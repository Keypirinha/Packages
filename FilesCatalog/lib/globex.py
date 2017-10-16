#
# Keypirinha: a fast launcher for Windows (keypirinha.com)
# Copyright 2013-2017 Jean-Charles Lefebvre <polyvertex@gmail.com>
#

import fnmatch
import os
import posixpath
import re
import stat
import sys

__all__ = ['globex', 'iglobex',
           'escape', 'has_magic', 'has_recursive_magic', 'is_hidden']

PY36 = sys.version_info >= (3, 6)
IS_WINDOWS = os.name == 'nt'

DOT = ('.', b'.'[0])
MAGIC_REGEX = re.compile('([*?[])')
MAGIC_REGEX_BYTES = re.compile(b'([*?[])')

if IS_WINDOWS:
    import ctypes

if __debug__:
    SEP = (os.sep, bytes(os.sep, 'utf-8')[0])
    if os.altsep:
        ALTSEP = (os.altsep, bytes(os.altsep, 'utf-8')[0])
    else:
        ALTSEP = ()

class GlobExEntry:
    """
    An :py:class:`os.DirEntry` compatible class.

    Additional features:

    * The ``depth`` attribute is an unsigned integer that indicates at which
      level of recursivity this entry has been found
    * The :py:meth:`is_hidden`, :py:meth:`exists` and :py:meth:`lexists` methods
    """
    def is_hidden(self):
        """Call :py:func:`globex.is_hidden` with this entry"""
        return is_hidden(self)

    def exists(self, follow_symlinks=True):
        """
        Check entry's existence by calling :py:meth:`stat` internally and return
        a boolean
        """
        try:
            self.stat(follow_symlinks=follow_symlinks)
            return True
        except OSError:
            return False

    def lexists(self):
        """Same as ``entry.exist(follow_symlinks=False)``"""
        return self.exists(follow_symlinks=False)

    def __str__(self):
        return self.path

    def __repr__(self):
        return '{}.{}({})'.format(
            self.__class__.__module__,
            self.__class__.__qualname__, #py3k
            repr(self.path))

    # os.DirEntry implements __fspath__() so we preserve interface compatibility
    if PY36:
        def __fspath__(self):
            return self.path

class _GlobExEntry_OsDirEntry(GlobExEntry):
    def __init__(self, direntry, depth=0):
        assert isinstance(direntry, os.DirEntry)
        assert depth >= 0
        self.direntry = direntry
        self.depth = depth

    def __getattr__(self, attr):
        try:
            return getattr(self.direntry, attr)
        except AttributeError:
            return super().__getattr__(attr)

class _GlobExEntry_Path(GlobExEntry):
    def __init__(self, path, basename=None, depth=0):
        assert isinstance(path, (str, bytes))
        assert basename is None or isinstance(basename, (str, bytes))
        assert basename is None or os.path.split(basename)[1] == basename
        assert depth >= 0

        if basename is None:
            # *path* is complete and self.name will be lazy-init by
            # __getattr__() if needed
            #assert not (path[-1] in SEP or path[-1] in ALTSEP)
            self.path = path if path else os.curdir
        else:
            # *basename* is provided and *path* is its dirname
            if __debug__:
                if isinstance(basename, bytes):
                    assert SEP[1] not in basename
                    assert ALTSEP[1] not in basename
                else:
                    assert SEP[0] not in basename
                    assert ALTSEP[0] not in basename
            self.path = os.path.join(path, basename) if path else basename
            self.name = basename

        self.depth = depth
        self._stat = None
        self._lstat = None

    def __getattr__(self, attr):
        if attr == 'name':
            self.name = os.path.basename(self.path)
            return self.name
        else:
            return super().__getattr__(attr)

    def inode(self):
        return self.stat(follow_symlinks=False).st_ino

    def is_dir(self, *, follow_symlinks=True):
        return stat.S_ISDIR(self.stat(follow_symlinks=follow_symlinks).st_mode)

    def is_file(self, *, follow_symlinks=True):
        return stat.S_ISREG(self.stat(follow_symlinks=follow_symlinks).st_mode)

    def is_symlink(self):
        return stat.S_ISLNK(self.stat(follow_symlinks=False).st_mode)

    def stat(self, *, follow_symlinks=True):
        if follow_symlinks:
            if not self._stat:
                self._stat = os.stat(self.path, follow_symlinks=True)
            return self._stat
        else:
            if not self._lstat:
                self._lstat = os.lstat(self.path)
            return self._lstat

def globex(pathname, *, recursivity=False, include_hidden=False):
    """
    Same as :py:func:`iglobex` but returns a list of :py:class:`GlobExEntry`
    objects instead of an iterator
    """
    return list(iglobex(pathname,
                        recursivity=recursivity,
                        include_hidden=include_hidden))

def iglobex(pathname, *, recursivity=False, include_hidden=False):
    """
    Imitate the behavior of :py:func:`glob.iglob` by finding all the entries of
    the filesystem that match a specified pattern (*pathname* argument)
    according to the rules used by the Unix shell.

    This function implements the following additional features compared to
    :py:func:`glob.iglob`:

    * *pathname* can be a path-like object (Python 3.6+)
    * Yields :py:class:`GlobExEntry` objects instead of pathnames
    * When enabled, the maximum level of recursivity can be specified (depth)
    * Hidden files can be included if desired
    * True handling of hidden files on Windows in addition to the original
      behavior, by checking file's attributes. This check comes for free in most
      cases (i.e. when entry is not a symlink).
      Original behavior was to check if basename starts with a dot.
    * Does not create intermediate lists internally

    Returns an iterator that yields :py:class:`GlobExEntry` objects.
    """
    # Support of path-like objects
    if PY36:
        pathname = os.fspath(pathname)

    # Normalize the recursivity value
    if recursivity is True:
        recursivity = -1
    elif not recursivity:
        recursivity = 0
    if not isinstance(recursivity, int):
        raise TypeError('recursivity must be an int or a bool')

    it = _iglobex(pathname, recursivity, include_hidden, False)
    if recursivity and _is_recursive(pathname):
        entry = next(it) # skip dummy entry
        assert len(entry.path) == 1 and entry.path[0] in DOT

    return it

def _iglobex(pathname, recursivity, include_hidden, dironly):
    dirname, basename = os.path.split(pathname)

    if not has_magic(pathname):
        assert not dironly
        if basename:
            entry = _GlobExEntry_Path(pathname)
            if entry.lexists():
                yield entry
        else:
            # Patterns ending with a slash should match only
            # directories (glob._iglob)
            if os.path.isdir(dirname):
                yield _GlobExEntry_Path(pathname)
        return

    if not dirname:
        if recursivity and _is_recursive(basename):
            yield from _glob2(dirname, basename, dironly,
                              recursivity, include_hidden)
        else:
            yield from _glob1(dirname, basename, dironly,
                              recursivity, include_hidden)
        return

    # os.path.split() returns the argument itself as a dirname if it is a drive
    # or UNC path.  Prevent an infinite recursion if a drive or UNC path
    # contains magic characters (i.e. r'\\?\C:').
    if dirname != pathname and has_magic(dirname):
        dirs = _iglobex(dirname, recursivity, include_hidden, True)
    else:
        dirs = (_GlobExEntry_Path(dirname), )

    if has_magic(basename):
        if recursivity and _is_recursive(basename):
            glob_in_dir = _glob2
        else:
            glob_in_dir = _glob1
    else:
        glob_in_dir = _glob0

    for entry in dirs:
        yield from glob_in_dir(entry.path, basename, dironly,
                               recursivity, include_hidden)

def has_magic(s):
    """
    Return ``True`` if the given string (`str` or `bytes`) contains any of the
    magic wildcards supported by :py:mod:`fnmatch`
    """
    if isinstance(s, bytes):
        match = MAGIC_REGEX_BYTES.search(s)
    else:
        match = MAGIC_REGEX.search(s)
    return match is not None

def has_recursive_magic(s):
    """
    Return ``True`` if the given string (`str` or `bytes`) contains the ``**``
    sequence
    """
    if isinstance(s, bytes):
        return b'**' in s
    else:
        return '**' in s

def _is_recursive(pattern):
    if isinstance(pattern, bytes):
        return pattern == b'**'
    else:
        return pattern == '**'

def escape(pathname):
    """
    Same as :py:func:`glob.escape`. Escape all special characters (``?``, ``*``
    and ``[``).

    This is useful if you want to match an arbitrary literal string that may
    have special characters in it. Special characters in drive/UNC sharepoints
    are not escaped, e.g. on Windows escape(``//?/c:/Quo vadis?.txt``) returns
    ``//?/c:/Quo vadis[?].txt``.
    """
    drive, pathname = os.path.splitdrive(pathname)
    if isinstance(pathname, bytes):
        pathname = MAGIC_REGEX_BYTES.sub(br'[\1]', pathname)
    else:
        pathname = MAGIC_REGEX.sub(r'[\1]', pathname)
    return drive + pathname

def is_hidden(pathname_or_entry):
    """
    Return a boolean value to indicate if *pathname_or_entry* is a hidden entry
    in the filesystem.

    A file is considered *hidden* if its name is prefixed by a dot character. On
    Windows, the `stat.FILE_ATTRIBUTE_HIDDEN` attribute is also checked.

    *pathname_or_entry* can be a :py:class:`str`, :py:class:`bytes`,
    :py:class:`GlobExEntry` or a :py:class:`os.DirEntry` object. It can also be
    a path-like object (Python 3.6+).

    On Windows and if *pathname_or_entry* is a :py:class:`GlobExEntry` or
    :py:class:`os.DirEntry` object, this check comes for free as long as the
    ``stat`` of the entry is already cached (i.e. most cases).

    May raise an `OSError` (on Windows) or a `TypeError` exception.
    """
    if isinstance(pathname_or_entry, (GlobExEntry, os.DirEntry)):
        if pathname_or_entry.name[0] in DOT:
            return True

        if IS_WINDOWS:
            # Use follow_symlinks=False to stay consistent with
            # GetFileAttributesW() that is called below
            st = pathname_or_entry.stat(follow_symlinks=False)
            if st.st_file_attributes & stat.FILE_ATTRIBUTE_HIDDEN:
                return True

        return False

    # Support of path-like objects
    # Reminder: os.DirEntry implements __fspath__() so this block must remain
    # after the isinstance(..., os.DirEntry) test above
    if PY36:
        pathname_or_entry = os.fspath(pathname_or_entry)

    if isinstance(pathname_or_entry, (str, bytes)):
        basename = os.path.basename(pathname_or_entry)
        if basename and basename[0] in DOT:
            return True

        if IS_WINDOWS:
            if isinstance(pathname_or_entry, bytes):
                path = os.fsdecode(pathname_or_entry)
            attr = ctypes.windll.kernel32.GetFileAttributesW(pathname_or_entry)
            err = ctypes.GetLastError() # call it as soon as possible
            if attr == 0xffffffff: # INVALID_FILE_ATTRIBUTES
                raise OSError(None, ctypes.FormatError(err),
                              pathname_or_entry, err)
            if attr & stat.FILE_ATTRIBUTE_HIDDEN:
                return True

        return False

    raise TypeError

def _glob0(dirname, basename, dironly, recursivity, include_hidden):
    if not basename:
        # os.path.split() returns an empty basename for paths ending with a
        # directory separator.  'q*x/' should match only directories.
        entry = _GlobExEntry_Path(dirname)
        try:
            if entry.is_dir():
                yield entry
        except OSError:
            pass
    else:
        entry = _GlobExEntry_Path(dirname, basename)
        if entry.lexists():
            yield entry

def _glob1(dirname, pattern, dironly, recursivity, include_hidden):
    # To optimize things a bit, instead of calling fnmatch.fnmatch() from each
    # iteration of the loop, we reproduce the behavior of fnmatch.filter()
    # here by compiling the given pattern once for all, then match it against
    # the entries yielded by _iterdir() on-the-fly.
    # This has the extra benefit of avoiding the creation of a temporary list.
    pattern = os.path.normcase(pattern)
    patmatch = fnmatch._compile_pattern(pattern)

    for entry in _iterdir(dirname, dironly, include_hidden, 0):
        if os.path is posixpath: # os.path.normcase() on posix is NOP
            if patmatch(entry.name):
                yield entry
        else:
            if patmatch(os.path.normcase(entry.name)):
                yield entry

def _glob2(dirname, pattern, dironly, recursivity, include_hidden):
    assert _is_recursive(pattern)
    yield _GlobExEntry_Path(dirname)
    yield from _riterdir(dirname, dironly, recursivity, include_hidden, 0)

def _glob3(dirname, pattern, dironly, recursivity, include_hidden):
    assert has_recursive_magic(pattern) and not _is_recursive(pattern)
    yield _GlobExEntry_Path(dirname)
    yield from _riterdir(dirname, dironly, recursivity, include_hidden, 0)

def _iterdir(dirname, dironly, include_hidden, depth):
    if not dirname:
        if isinstance(dirname, bytes):
            dirname = bytes(os.curdir, 'ASCII')
        else:
            dirname = os.curdir

    try:
        with os.scandir(dirname) as it:
            for entry in it:
                try:
                    if not include_hidden and is_hidden(entry):
                        continue
                    if dironly and not entry.is_dir():
                        continue
                except OSError:
                    pass

                yield _GlobExEntry_OsDirEntry(entry, depth=depth)
    except OSError:
        return

def _riterdir(dirname, dironly, recursivity, include_hidden, depth):
    assert recursivity
    for entry in _iterdir(dirname, dironly, include_hidden, depth):
        yield entry
        if recursivity < 0 or depth < recursivity:
            for subentry in _riterdir(entry.path, dironly, recursivity,
                                      include_hidden, depth + 1):
                yield subentry


if __name__ == '__main__':
    import argparse
    import sys

    argp = argparse.ArgumentParser()
    argp.add_argument('-r', '--recursivity', type=int, default=0,
        help='Recursivity level in [-1, ...]')
    argp.add_argument('--hidden', action='store_true',
        help='List hidden filesystem entries')
    argp.add_argument('patterns', nargs=argparse.REMAINDER,
        help='The paths/patterns to glob')

    if len(sys.argv) < 2:
        argp.print_help()
        sys.exit(2)
    args = argp.parse_args()

    if __debug__:
        sys.stderr.write('DEBUG mode\n')
        sys.stderr.flush()

    first = True
    for pattern in args.patterns:
        if first:
            first = False
        else:
            sys.stdout.write('\n' + ('-' * 30) + '\n\n')

        sys.stdout.write('***** ' + pattern + '\n')
        sys.stdout.flush()

        for entry in iglobex(pattern, recursivity=args.recursivity,
                             include_hidden=args.hidden):
            assert isinstance(entry, GlobExEntry)
            sys.stdout.write('  [+] [{}] {}\n'.format(entry.depth, repr(entry)))
