#
# Placeholder Python module for user's callback(s).
#
# Copy this file into the "Profile\Packages\FilesCatalog" folder so Keypirinha
# can load your callback(s) at runtime. You may need to create the
# "FilesCatalog" folder first.
#
# Your callback(s) can have any arbitrary name as long as it is supported by the
# Python language and that you reference it using the *python_callback* setting.
#
# CAUTION: bear in mind that this function will be called for every single entry
# of the filesystem from the scan loop so you may want to keep it as lightweight
# as possible in terms of speed and I/O access.
#
# For convenience, filescatalog.py monkey-patches this module to declare the
# following variables so you have access to some filescatalog's tools that may
# come handy during the development of your callback:
#   * _filefilter: the *filefilter* module (in filescatalog's "lib" directory)
#   * _globex: the *globex* module (in filescatalog's "lib" directory)
#   * _TEMPLATE_TAG_SEP: filescatalog's *TEMPLATE_TAG_SEP* constant
#   * _TEMPLATE_TAG_REGEX: filescatalog's *TEMPLATE_TAG_REGEX* constant
#   * _LazyItemLabelFormatter: filescatalog's *LazyItemLabelFormatter* class
#   * _default_scan_callback: filescatalog's own callback named
#       *default_scan_callback* that you may want to call from your function as
#       a fallback method for example
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
#    for filter in profile.filters:
#        if filter.match(entry):
#            if not filter.inclusive:
#                return None
#            break
#
#    if entry.is_dir():
#        item_label_tmpl = profile.dir_item_label
#    else:
#        item_label_tmpl = profile.file_item_label
#
#    formatter = _LazyItemLabelFormatter(entry, profile, plugin)
#    item_label = formatter.format(item_label_tmpl)
#
#    return plugin.create_item(
#        category=kp.ItemCategory.FILE,
#        label=item_label,
#        short_desc="", # path is displayed on GUI if desc is empty
#        target=entry.path,
#        args_hint=kp.ItemArgsHint.ACCEPTED,
#        hit_hint=kp.ItemHitHint.KEEPALL)
