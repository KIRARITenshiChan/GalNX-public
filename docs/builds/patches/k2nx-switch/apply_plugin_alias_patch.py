
import io, sys
p = r"E:/galnx-build/pilot-01/k2nx-ws/src/src/plugins/InternalPlugins.cpp"
data = open(p,'rb').read()
old = b'''bool TVPLoadInternalPlugin(const ttstr &_name)\r\n{\r\n\treturn ncbAutoRegister::LoadModule(TVPExtractStorageName(_name));\r\n}'''
new = b'''bool TVPLoadInternalPlugin(const ttstr &_name)\r\n{\r\n\t// [GalNX] Games ship their plugins as plugin/*.tpm while the built-in modules\r\n\t// (windowEx, layerExImage, fstat, extrans, csvParser, ...) register under *.dll.\r\n\t// Without this alias the game's own plugin folder can never reach the built-in\r\n\t// ports, so scripts fail with "Member ... does not exist" (e.g. KAG\r\n\t// Window.registerExEvent). Try the requested name first, then *.tpm -> *.dll.\r\n\tttstr name = TVPExtractStorageName(_name);\r\n\tif (ncbAutoRegister::LoadModule(name)) {\r\n\t\tprintf("[GalNX] internal plugin loaded: %s\\n", name.AsNarrowStdString().c_str());\r\n\t\treturn true;\r\n\t}\r\n\tttstr lower = name.AsLowerCase();\r\n\tif (lower.GetLen() > 4 && lower.SubString(lower.GetLen() - 4, 4) == TJS_W(".tpm")) {\r\n\t\tttstr dll(name.SubString(0, name.GetLen() - 4));\r\n\t\tdll += TJS_W(".dll");\r\n\t\tif (ncbAutoRegister::LoadModule(dll)) {\r\n\t\t\tprintf("[GalNX] internal plugin loaded via .tpm alias: %s -> %s\\n",\r\n\t\t\t       name.AsNarrowStdString().c_str(), dll.AsNarrowStdString().c_str());\r\n\t\t\treturn true;\r\n\t\t}\r\n\t\tprintf("[GalNX] no built-in module for game plugin: %s\\n", name.AsNarrowStdString().c_str());\r\n\t} else {\r\n\t\tprintf("[GalNX] no built-in module for plugin: %s\\n", name.AsNarrowStdString().c_str());\r\n\t}\r\n\treturn false;\r\n}'''
if old not in data:
    print("OLD NOT FOUND"); sys.exit(1)
data = data.replace(old, new)
# ensure <cstdio>
inc_old = b'#include "ncbind/ncbind.hpp"\r\n'
if b'#include <cstdio>' not in data:
    data = data.replace(inc_old, inc_old + b'#include <cstdio>\r\n', 1)
open(p,'wb').write(data)
print("PATCHED", len(data))
