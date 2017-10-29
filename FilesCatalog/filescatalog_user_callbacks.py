#
# Placeholder Python module for user's callback(s).
#
# Copy this file into the "Profile\Packages\FilesCatalog" folder so Keypirinha
# can load your callback(s) at runtime.
# You may need to create the "FilesCatalog" folder first.
#
# Your callbacks can have any arbitrary name that is supported by the Python
# language. Do not forget to reference them using the *python_callback* setting.
#
# CAUTION: bear in mind the callback function is called for every single
# filesystem entry from the scan loop so you probably want to keep it as
# lightweight as possible in terms of speed and I/O access.
#
# For convenience, right after the import statement of this module,
# filescatalog.py monkey-patches this module to declare the following variables
# so you have access to some filescatalog's tools that may come handy during the
# development of your callback:
#   * _filefilter: the *filefilter* module (in filescatalog's "lib" directory)
#   * _globex: the *globex* module (in filescatalog's "lib" directory)
#   * _TEMPLATE_TAG_SEP: filescatalog's *TEMPLATE_TAG_SEP* constant
#   * _TEMPLATE_TAG_REGEX: filescatalog's *TEMPLATE_TAG_REGEX* constant
#   * _LazyItemLabelFormatter: filescatalog's *LazyItemLabelFormatter* class
#   * _default_scan_callback: filescatalog's own callback named
#       *default_scan_callback* that you may want to call from your function as
#       a fallback method for example
#
# Because those variables are not defined yet at import time, it is possible to
# implement a ``on_imported()`` function that will be called right after this
# module has been monkey-patch.
# No return value is expected from it.
#
# As an example, here is how a callback function could be implemented.
# This code mimics the default callback implemented in filescatalog.py:
#
#import keypirinha as kp
#
#def my_callback(entry, profile, plugin):
#    if not profile.include_hidden and entry.is_hidden():
#        return None
#    if not profile.include_dirs and entry.is_dir():
#        return None
#    if not profile.include_files and not entry.is_dir():
#        return None
#
#    if profile.filters:
#        matched = False
#        for filter in profile.filters:
#            # note: a filter returns None on error
#            if filter.match(entry):
#                if not filter.inclusive:
#                    return None
#                matched = True
#                break
#
#        # apply default behavior if entry did not match any filter
#        if not matched and not profile.filters_default:
#            return None
#
#    if entry.is_dir():
#        item_label_tmpl = profile.dir_item_label
#        item_desc_tmpl = profile.dir_item_desc
#    else:
#        item_label_tmpl = profile.file_item_label
#        item_desc_tmpl = profile.file_item_desc
#
#    formatter = _LazyItemLabelFormatter(entry, profile, plugin)
#    item_label = formatter.format(item_label_tmpl, fallback=entry.name)
#    item_desc = formatter.format(item_desc_tmpl, fallback="")
#
#    return plugin.create_item(
#        category=kp.ItemCategory.FILE,
#        label=item_label,
#        short_desc=item_desc, # path is displayed on GUI if desc is empty
#        target=entry.path,
#        args_hint=kp.ItemArgsHint.ACCEPTED,
#        hit_hint=kp.ItemHitHint.KEEPALL)
