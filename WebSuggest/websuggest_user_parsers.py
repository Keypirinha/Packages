#
# Placeholder Python module for additional response parsers.
#
# Copy this file into the "Profile\Packages\WebSuggest" folder so Keypirinha
# can load your callback(s) at runtime.
# You may need to create the "WebSuggest" folder first.
#
# Your functions can have any arbitrary name that is supported by the Python
# language. Do not forget to reference them using the *api_parser* setting.
#
# Here is how the default "opensearch" parser is implemented:
#
#import json
#import traceback
#
#def my_parser(plugin, provider, response):
#    try:
#        response = response.decode(encoding="utf-8", errors="strict")
#        return json.loads(response)[1]
#    except:
#        plugin.warn("Failed to parse response from provider {}.".format(
#                    provider.label))
#        traceback.print_exc()
#        return []
