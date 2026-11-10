import sys
ROOT = 'E:/galnx-build/m1-krkrsdl2/'
T = chr(9)
NL = chr(10)

def patch(rel, old, new, label):
    p = ROOT + rel
    raw = open(p, 'rb').read().decode('utf-8')
    crlf = ('\r\n' in raw)
    txt = raw.replace('\r\n', '\n')
    c = txt.count(old)
    if c != 1:
        print('FAIL', label, 'count=', c)
        sys.exit(1)
    txt = txt.replace(old, new, 1)
    out = txt.replace('\n', '\r\n') if crlf else txt
    open(p, 'wb').write(out.encode('utf-8'))
    print('OK', label)

# F1: Citron delivers argc==0; KiriKiri needs argv[0] as exe path.
old1 = T + '_argc = argc;' + NL + T + '_wargv = new tjs_char*[argc];' + NL
new1 = (T + '_argc = argc;' + NL + T + '_wargv = new tjs_char*[argc];' + NL + NL
        + T + '#ifdef __SWITCH__' + NL
        + T + 'if (argc <= 0 || argv == NULL || argv[0] == NULL || argv[0][0] == 0)' + NL
        + T + '{' + NL
        + T + T + '// GALNX: emulators (Citron/Ryujinx) may pass argc == 0; KiriKiri uses argv[0] as ExePath.' + NL
        + T + T + 'static char *galnx_default_argv[1] = { (char *)"sdmc:/switch/galnx/app.nro" };' + NL
        + T + T + 'argc = 1;' + NL
        + T + T + 'argv = galnx_default_argv;' + NL
        + T + '}' + NL
        + T + '#endif' + NL)
patch('src/core/sdl2/SDLApplication.cpp', old1, new1, 'F1 argv fallback')

# F2: ExePath() safety fallback on Switch (if _wargv is still empty).
old2 = (('#ifndef __EMSCRIPTEN__' + NL)
        + T + 'if (exepath.empty())' + NL + T + '{' + NL + T + T + 'exepath = tjs_string(_wargv[0]);' + NL + T + '}' + NL
        + '#endif' + NL + T + 'return exepath;')
new2 = (T + '#ifdef __SWITCH__' + NL
        + T + 'if (exepath.empty())' + NL
        + T + '{' + NL
        + T + T + 'exepath = tjs_string(TJS_W("sdmc:/switch/galnx/app.nro"));' + NL
        + T + '}' + NL
        + T + '#else' + NL
        + '#ifndef __EMSCRIPTEN__' + NL
        + T + 'if (exepath.empty())' + NL + T + '{' + NL + T + T + 'exepath = tjs_string(_wargv[0]);' + NL + T + '}' + NL
        + '#endif' + NL
        + T + '#endif' + NL + T + 'return exepath;')
patch('src/core/environ/sdl2/Application.cpp', old2, new2, 'F2 ExePath fallback')

# F3: SDL_GetBasePath() returns NULL on Switch; NRO assets live at romfs:/.
old3 = (T + 'if (base_path)' + NL + T + '{' + NL + T + T + 'base_path_utf8 = base_path;' + NL + T + T + 'SDL_free(base_path);' + NL + T + '}' + NL + '#ifdef __ANDROID__')
new3 = (T + 'if (base_path)' + NL + T + '{' + NL + T + T + 'base_path_utf8 = base_path;' + NL + T + T + 'SDL_free(base_path);' + NL + T + '}' + NL
        + T + '#ifdef __SWITCH__' + NL
        + T + '// GALNX: SDL_GetBasePath() returns NULL on Switch; NRO assets are mounted at romfs:/.' + NL
        + T + 'if (base_path_utf8.length() == 0)' + NL + T + '{' + NL + T + T + 'base_path_utf8 = "romfs:/";' + NL + T + '}' + NL
        + T + '#endif' + NL + '#ifdef __ANDROID__')
patch('src/core/base/sdl2/SysInitImpl.cpp', old3, new3, 'F3 romfs base path')

# F4: strip the file://?/ marker so native Switch paths reach stat()/fopen().
old4 = 'void TJS_INTF_METHOD tTVPFileMedia::GetLocallyAccessibleName(ttstr &name)' + NL + '{' + NL
new4 = (old4 + '#ifdef __SWITCH__' + NL
        + T + '{' + NL
        + T + T + '// GALNX: TVPPreNormalizeStorageName wraps native Switch paths (romfs:/..., sdmc:/...)' + NL
        + T + T + '// as file://?/<native>. Strip the "?/" marker so the native path reaches stat()/fopen().' + NL
        + T + T + 'tjs_string galnx_wname(name.AsStdString());' + NL
        + T + T + 'std::string galnx_nname;' + NL
        + T + T + 'if (TVPUtf16ToUtf8(galnx_nname, galnx_wname) && galnx_nname.size() >= 2 && galnx_nname[0] == (char)63 && galnx_nname[1] == (char)47)' + NL
        + T + T + '{' + NL
        + T + T + T + 'tjs_string galnx_sub = galnx_wname.substr(2);' + NL
        + T + T + T + 'name = ttstr(galnx_sub);' + NL
        + T + T + T + 'return;' + NL
        + T + T + '}' + NL
        + T + '}' + NL
        + '#endif' + NL)
patch('src/core/base/sdl2/StorageImpl.cpp', old4, new4, 'F4 storage native prefix')
print('ALL CLEAN FIXES APPLIED')