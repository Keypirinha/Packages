#
# Keypirinha: a fast launcher for Windows (keypirinha.com)
# Copyright 2013-2017 Jean-Charles Lefebvre <polyvertex@gmail.com>
#

import fnmatch
import glob
import os
import re
import stat
import sys

__all__ = ['create_filter', 'AttrFilter', 'PathFilter']

PY36 = sys.version_info >= (3, 6)
IS_WINDOWS = os.name == 'nt'

EXPRESSION_REGEX = re.compile(
    r"""
        ^\s*
        (?:([+-])\s+)?
        (?:\:?([a-z_\:]{2,})\:\s+)?
        (.+)
        (?<!\s)\s*$
    """, flags=re.VERBOSE)

if IS_WINDOWS:
    import ctypes
    from collections import OrderedDict

    WIN_FILE_ATTRIBUTE = OrderedDict((
        ('directory', stat.FILE_ATTRIBUTE_DIRECTORY),
        ('dir', stat.FILE_ATTRIBUTE_DIRECTORY),

        ('hidden', stat.FILE_ATTRIBUTE_HIDDEN),

        ('symlink', stat.FILE_ATTRIBUTE_REPARSE_POINT),
        ('reparse_point', stat.FILE_ATTRIBUTE_REPARSE_POINT),

        ('compressed', stat.FILE_ATTRIBUTE_COMPRESSED),
        ('comp', stat.FILE_ATTRIBUTE_COMPRESSED),

        ('archive', stat.FILE_ATTRIBUTE_ARCHIVE),
        ('arch', stat.FILE_ATTRIBUTE_ARCHIVE),
        ('arc', stat.FILE_ATTRIBUTE_ARCHIVE),

        #('device', stat.FILE_ATTRIBUTE_DEVICE),
        #('dev', stat.FILE_ATTRIBUTE_DEVICE),

        ('encrypted', stat.FILE_ATTRIBUTE_ENCRYPTED),

        ('readonly', stat.FILE_ATTRIBUTE_READONLY),
        ('ro', stat.FILE_ATTRIBUTE_READONLY),

        ('system', stat.FILE_ATTRIBUTE_SYSTEM),
        ('sys', stat.FILE_ATTRIBUTE_SYSTEM)))


class Filter:
    def __init__(self, inclusive):
        self.hash_cache = None
        self.inclusive = inclusive

    def match(self, *unused_args, **unused_kwargs):
        raise NotImplementedError

    def __hash__(self):
        raise NotImplementedError

    def __eq__(self, other):
        raise NotImplementedError

if IS_WINDOWS:
    class WinAttrFilter(Filter):
        def __init__(self, pattern, match_all=False, inclusive=True):
            super().__init__(inclusive)

            self.match_all = match_all
            self.desired_attr = 0
            self.not_desired_attr = 0

            pattern = pattern.lower().split()
            for attr_str in pattern:
                if attr_str:
                    desired = True
                    if attr_str[0] == '!':
                        desired = False
                        attr_str = attr_str.lstrip('!')

                    try:
                        attr_flag = WIN_FILE_ATTRIBUTE[attr_str]
                    except KeyError:
                        raise ValueError('unknown file attribute "{}"'.format(
                            attr_str))

                    if desired:
                        self.desired_attr |= attr_flag
                    else:
                        self.not_desired_attr |= attr_flag

            if not self.desired_attr and not self.not_desired_attr:
                raise ValueError('empty attr or attr_all filter')

            if (self.desired_attr & self.not_desired_attr) != 0:
                raise ValueError(
                    'colliding attribute(s) found in attr or attr_all filter')

        def __hash__(self):
            # CAUTION: for this to be consistent, object must be immutable
            if self.hash_cache is None:
                self.hash_cache = hash((self.inclusive, self.match_all,
                                        self.desired_attr,
                                        self.not_desired_attr))
            return self.hash_cache

        def __eq__(self, other):
            if isinstance(other, self.__class__):
                return hash(self) == hash(other)
            return NotImplemented

        def __str__(self):
            s = '+ ' if self.inclusive else '- '
            s += 'attr_all:' if self.match_all else 'attr:'

            desired_attr = self.desired_attr
            not_desired_attr = self.not_desired_attr
            for attr_name, attr_flag in WIN_FILE_ATTRIBUTE.items():
                if desired_attr & attr_flag:
                    s += ' ' + attr_name
                    desired_attr &= ~attr_flag
                elif not_desired_attr & attr_flag:
                    s += ' !' + attr_name
                    not_desired_attr &= ~attr_flag

            return s

        def match(self, path_or_entry, **unused_kwargs):
            # Assume first that *path_or_entry* is `globex.GlobExEntry` object
            # or any other `os.DirEntry`-compatible
            try:
                file_attr = path_or_entry.stat(
                    follow_symlinks=False).st_file_attributes
            except OSError:
                return None
            except: # AttributeError, TypeError, ... We are really blind here
                if PY36:
                    path_or_entry = os.fspath(path_or_entry)
                if isinstance(path_or_entry, bytes):
                    path_or_entry = os.fsdecode(path_or_entry)
                file_attr = ctypes.windll.kernel32.GetFileAttributesW(
                    path_or_entry)
                if file_attr == 0xffffffff: # INVALID_FILE_ATTRIBUTES
                    return None

            # A file is considered *hidden* if it has the *hidden* attribute or
            # if its name starts with a '.' character.
            if not (file_attr & stat.FILE_ATTRIBUTE_HIDDEN):
                if isinstance(path_or_entry, bytes):
                    if path_or_entry[0] == b'.'[0]:
                        file_attr |= stat.FILE_ATTRIBUTE_HIDDEN
                elif path_or_entry[0] == '.':
                    file_attr |= stat.FILE_ATTRIBUTE_HIDDEN

            match = file_attr & self.desired_attr
            not_match = file_attr & self.not_desired_attr

            if self.match_all:
                return match == self.desired_attr and not_match == 0
            else:
                return match or (self.not_desired_attr != 0 and
                                 not_match != self.not_desired_attr)

class PathFilter(Filter):
    def __init__(self, pattern, regex=False, inclusive=True):
        super().__init__(inclusive)
        self.pattern = None # kept for __eq__, __str__ and match()
        self.regex = regex # kept for __str__ and optionally for match()
        self.patmatch = None
        self.splits = 0 # 0: name only; >0: path tail

        # Compile the pattern.  *pattern* can be a regex, a shell-like pattern
        # or a raw string.  A regex always matches the basename only.
        if regex:
            self.pattern = pattern
            try:
                self.patmatch = re.compile(pattern, flags=re.IGNORECASE).match
            except Exception as exc:
                raise ValueError('invalid regex: {}'.format(exc))
        else:
            pattern = os.path.normpath(pattern)
            drive, pattern = os.path.splitdrive(pattern)
            pattern = os.path.normcase(pattern)

            if drive or os.path.isabs(pattern):
                raise ValueError('absolute path found in filter')
            if not pattern:
                raise ValueError('invalid pattern format')

            if os.sep in pattern:
                self.splits = pattern.count(os.sep)
                # Ensure we match the full name of the first element in the
                # pattern
                pattern = os.sep + pattern

            self.pattern = pattern

            if glob.has_magic(pattern):
                # Note: the regex returned by fnmatch.translate() matches the
                # **end** of an expression thanks to ``\Z`` special sequence.
                # This is what we want.
                self.patmatch = re.compile(fnmatch.translate(pattern)).match
            else:
                self.patmatch = pattern

        assert callable(self.patmatch) or isinstance(self.patmatch, str)

    def __hash__(self):
        # CAUTION: for this to be consistent, object must be immutable
        if self.hash_cache is None:
            self.hash_cache = hash((self.inclusive, self.splits, self.pattern))
        return self.hash_cache

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return hash(self) == hash(other)
        return NotImplemented

    def __str__(self):
        s = '+ ' if self.inclusive else '- '
        s += 'regex: ' if self.regex else ''
        s += self.pattern
        return s

    def match(self, path, *, normalized=False, **unused_kwargs):
        """
        Return a boolean that indicates if the given *path* matches the pattern
        of this filter.

        *path* can be a `str`, `bytes` or a path-like object.

        If *normalized* is true, *path* must be a `str` that is the result of a
        call to `os.path.normpath` **and** `os.path.normcase`. This saves some
        execution time.
        """
        # Handle this special case to optimize things a bit.
        # * re.compile('*') raises an exception so we can be sure that the
        #   initial expression was not a regex
        # * However the (not self.regex) test may improve speed in some cases
        if not self.regex and self.pattern == '*':
            return True

        if not normalized:
            if PY36:
                path = os.fspath(path)
            path = os.path.normpath(path) # This also removes the trailing sep

        if isinstance(path, bytes):
            path = os.fsdecode(path)

        assert isinstance(path, str)

        if self.splits == 0: # match name only
            tail = os.path.basename(path)
            if not tail:
                return False
        else:
            # self.patmatch does not contain the drive part
            tail = os.path.splitdrive(path)[1]
            if not tail:
                return False
            if tail[0] != os.sep:
                # ensure the pattern matches the full name of the first element
                tail = os.sep + tail

            # Is given path shorter than the pattern?
            # Note: "+ 1" because of the front separator
            if tail.count(os.sep) < self.splits + 1:
                return False

            # lstrip the tail so we match only what we have to
            pos = len(tail)
            for idx in range(self.splits + 1):
                pos = tail.rindex(os.sep, 0, pos - 1)
            if pos > 0:
                tail = tail[pos:] # We want to keep the front sep

        if not normalized:
            tail = os.path.normcase(tail)

        if callable(self.patmatch):
            return bool(self.patmatch(tail))
        else:
            assert isinstance(self.patmatch, str)
            delta = len(tail) - len(self.patmatch)
            if delta > 0:
                return tail.endswith(self.patmatch)
            elif delta < 0:
                return False
            else:
                return tail == self.patmatch

class ExtensionsFilter(Filter):
    def __init__(self, pattern, inclusive=True):
        super().__init__(inclusive)
        pattern = os.path.normcase(pattern)
        if os.sep in pattern:
            raise ValueError('invalid or empty ext filter')
        self.ext = frozenset(filter(None, re.split(r'[\s\;]+', pattern)))

    def __hash__(self):
        # CAUTION: for this to be consistent, object must be immutable
        if self.hash_cache is None:
            self.hash_cache = hash((self.inclusive, self.ext))
        return self.hash_cache

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return hash(self) == hash(other)
        return NotImplemented

    def __str__(self):
        s = '+ ' if self.inclusive else '- '
        s += 'ext: '
        s += ' '.join(self.ext)
        return s

    def match(self, path_or_entry, **unused_kwargs):
        if not self.ext:
            return False

        # Assume first that *path_or_entry* is `globex.GlobExEntry` object or
        # any other `os.DirEntry`-compatible
        try:
            basename = path_or_entry.name
        except AttributeError:
            if PY36:
                path_or_entry = os.fspath(path_or_entry)
            basename = os.path.basename(path_or_entry)

        if isinstance(basename, bytes):
            basename = os.fsdecode(basename)

        basename = os.path.normcase(basename)

        for ext in self.ext:
            if basename.endswith(ext):
                return True

        return False


def create_filter(expression):
    rem = EXPRESSION_REGEX.match(expression)
    if not rem:
        raise ValueError('invalid filter expression')

    inclusive = False if rem.group(1) == '-' else True
    props = rem.group(2)
    if not props:
        props_orig = ()
        props = ()
    else:
        props_orig = props[:]
        props = props.lower().split(':')
    pattern = rem.group(3)
    is_regex = False
    is_attr_or = False
    is_attr_and = False
    is_ext = False

    assert pattern == pattern.strip()

    for prop in props:
        if not prop:
            pass
        elif prop in ('re', 'regex'):
            is_regex = True
        elif prop == 'attr':
            is_attr_or = True
        elif prop == 'attr_all':
            is_attr_and = True
        elif prop == 'ext':
            is_ext = True
        else:
            raise ValueError('invalid property "{}"'.format(prop))

    if sum((is_regex, is_attr_or, is_attr_and, is_ext)) > 1:
        raise ValueError('invalid mix of filter properties "{}"'.format(
                         props_orig))

    if is_ext:
        return ExtensionsFilter(pattern, inclusive=inclusive)
    elif is_attr_or or is_attr_and:
        if IS_WINDOWS:
            return WinAttrFilter(pattern, match_all=is_attr_and,
                                 inclusive=inclusive)
        else:
            raise NotImplementedError # TODO
    else:
        return PathFilter(pattern, regex=is_regex, inclusive=inclusive)


if __name__ == '__main__':
    # Keep this __debug__ test constant so it can be stripped by the compiler in
    # non-debug mode
    if __debug__:
        print('DEBUG mode', flush=True)

        # raw string filtering (name only)
        pf = create_filter('test')
        assert isinstance(pf, PathFilter)
        assert pf.inclusive
        assert not pf.regex
        assert pf.splits == 0
        assert isinstance(pf.patmatch, str)
        assert pf.match('test')
        assert pf.match('test', normalized=True)
        assert pf.match('TeSt') or os.name != 'nt'
        assert pf.match('TeSt', normalized=True) == False
        assert pf.match('/test')
        assert pf.match('/test/')
        assert pf.match('/test/', normalized=True) == False
        assert pf.match(r'c:\test')
        assert pf.match('c:/test/')
        assert pf.match('D:/test')
        assert pf.match('testt') == False

        # raw string filtering (dir + name)
        pf = create_filter('dir/test')
        assert isinstance(pf, PathFilter)
        assert pf.inclusive
        assert not pf.regex
        assert pf.splits == 1
        assert pf.match(r'c:\foo\dir\test\\')
        assert pf.match(r'c:\foo\_dir\test') == False

        # absolute path filters are not supported
        for s in ('/test', 'c:/test', r'\\?\c:\test', r'\\server\share\dir'):
            try:
                pf = create_filter(s)
                assert isinstance(pf, PathFilter)
            except ValueError as exc:
                assert 'absolute' in str(exc)
                continue # ok
            assert 0 # we should never get here

        # shell-like pattern filtering (name only)
        pf = create_filter('t?st')
        assert isinstance(pf, PathFilter)
        assert pf.inclusive
        assert not pf.regex
        assert pf.splits == 0
        assert pf.match('test')
        assert pf.match('tst') == False

        # shell-like pattern filtering (dir + name)
        pf = create_filter('dir/t?st')
        assert isinstance(pf, PathFilter)
        assert pf.inclusive
        assert not pf.regex
        assert pf.splits == 1
        assert pf.match('dir/test')
        assert pf.match(r'c:\foo\dir\test')
        assert pf.match(r'c:\foo\dir\test\\')
        assert pf.match(r'c:\foo\_dir\test') == False
        assert pf.match('dir') == False
        assert pf.match('test') == False

        # shell-like pattern filtering (dir + name) (part 2)
        pf = create_filter('dir/*')
        assert isinstance(pf, PathFilter)
        assert pf.inclusive
        assert not pf.regex
        assert pf.splits == 1
        assert pf.match('dir/test')
        assert pf.match(r'\dir\test')
        assert pf.match(r'c:\foo\dir\test')
        assert pf.match(r'c:\foo\dir\test\\')
        assert pf.match(r'c:\foo\_dir\test') == False
        assert pf.match('dir') == False
        assert pf.match('test') == False

        # regex pattern filtering (always name only)
        pf = create_filter('regex: .*t.st.*')
        assert isinstance(pf, PathFilter)
        assert pf.inclusive
        assert pf.regex
        assert pf.splits == 0
        assert pf.match('test')
        assert pf.match('test world')
        assert pf.match('hello test')
        assert pf.match('hello test world')
        assert pf.match(r'c:\foo\dir\test')
        assert pf.match(r'c:\foo\dir\test\\')
        assert pf.match(r'c:\foo\test\bar') == False

        # regex pattern filtering (always name only) (part 2)
        pf = create_filter('regex: .*t.st\\.doc')
        assert isinstance(pf, PathFilter)
        assert pf.inclusive
        assert pf.regex
        assert pf.splits == 0
        assert pf.match('test') == False
        assert pf.match('test.doc')
        assert pf.match('tEst.doc')
        assert pf.match('tOst.doc')
        assert pf.match('hello tost.doc')
