#!/usr/bin/python2
import cookielib
import json, os, re, readline, sys, traceback, urllib, urllib2
from getpass import getpass

ENCODINGS = ['utf8', 'cp1251']

PATTERN = re.compile('\${.*?}')
LAMBDA = type(lambda: 0)
RE_SPACE = re.compile('.*\s+$', re.M)

LEVEL_SILENT, LEVEL_MODEST, LEVEL_DETAILED, LEVEL_VERBOSE = 0, 1, 2, 3

C_KEY   = 'key'
C_VALUE = 'value'
C_WORD  = 'word'
C_TEXT  = 'text'

class CriticalException(BaseException): pass

class NoRedirection(urllib2.HTTPErrorProcessor):
    def http_response(self, req, resp): return resp
    https_response = http_response

class Completer(object):
    def complete(self, text, state):
        buf = readline.get_line_buffer()
        line = readline.get_line_buffer().split()
        # show all commands
        if not line:
            return [c + ' ' for c in funcs][state]
        # account for last argument ending in a space
        if RE_SPACE.match(buf): line.append('')
        # resolve command to the implementation function
        cmd = line[0].strip()
        if cmd in funcs:
            impl = getattr(self, 'complete_%s' % cmd)
            args = line[1:]
            if args: return (impl(args) + [None])[state]
            return [cmd + ' '][state]
        results = [c + ' ' for c in funcs if c.startswith(cmd)] + [None]
        return results[state]


def guess_encoding(string):
    for encoding in ENCODINGS:
        try: return string.decode(encoding)
        except ValueError: pass
    return string


def output(*args):
    color_table = {
        C_KEY: (106, 135, 89),
        C_VALUE: (104, 151, 187),
        C_WORD: (187, 181, 41),
        C_TEXT: (204, 120, 50),

        'error': (255, 107, 104),
        'info': (83, 148, 236),
        'response': (0, 127, 127),
        'warning': (205, 205, 0)
    }
    csi = '\x1B['
    for x in args: sys.stdout.write(x if isinstance(x, basestring) else ''.join((csi, '38;2;{};{};{}m'.format(*color_table[x[0]]), guess_encoding(str(x[1])), csi, '0m')))
    print


def die(message):
    output(('error', 'CRITICAL ERROR:\n  {}'.format(message)))
    raise CriticalException


def split(string):
    return [x[1:-1] if x.startswith("'") and x.endswith("'") else x for x in re.split("( |'.*?')", string) if x.strip()]

def print_map(map):
    if map:
        l = max([len(x) for x in map])
        for x in sorted(map.keys()):
            output(('key', '{1:{0}}'.format(l, x)), ('value', ': {}'.format(map[x])))

def request(method, url, body, verbosity):
    variables['url'] = url
    levels = {
        'silent': LEVEL_SILENT,
        'modest': LEVEL_MODEST,
        'detailed': LEVEL_DETAILED,
        'full': LEVEL_VERBOSE
    }
    if verbosity not in levels: die('{} is not a valid verbosity level, choose from: {}'.format(verbosity, ', '.join(levels.keys())))
    level = levels[verbosity]

    method = method.upper()
    if level >= LEVEL_MODEST: output((C_WORD, method), ' ', (C_TEXT, url))
    if body: headers['Content-Length'] = len(body)
    elif 'Content-Length' in headers: del headers['Content-Length']

    req = urllib2.Request(url, body, headers)
    req.get_method = lambda: method

    if level >= LEVEL_DETAILED:
        print_map(headers)
        if body: output(('info', body))

    try:
        cj = cookielib.CookieJar()
        opener = urllib2.build_opener(NoRedirection, urllib2.HTTPCookieProcessor(cj))
        urllib2.build_opener = lambda *handlers: opener

        response = urllib2.urlopen(req)
    except urllib2.HTTPError as response: pass

    if level >= LEVEL_MODEST: output((C_WORD, response.code), ' ', (C_TEXT, response.msg))

    if level >= LEVEL_DETAILED: print_map(response.headers)
    body = response.read()
    try:
        body = json.loads(body)
        if level >= LEVEL_DETAILED: output(('response', json.dumps(body, sort_keys=True, indent=2, separators=(',', ':'))))
    except ValueError:
        if level >= LEVEL_DETAILED: output(('response', body))

    variables['response']['body'] = body

    if 300 <= response.code < 400: request('get', response.headers['Location'], None, verbosity)


def re_extract(string, prefix, re_values, re_names):
    values = re.compile(re_values).findall(string)
    if re_names is None:
        times = len(values)
        if times != 1: die('{} found {} times'.format(re_values, times) + (', '.join(values) if times > 1 else ''))
        variables[prefix] = values[0]
    else:
        for k, v in zip(re.compile(re_names).findall(string), values): variables['-'.join((prefix, k))] = v


def form(method, url, prefix, verbosity):
    skip, data = len(prefix) + 1, {}
    for v in variables:
        if v.startswith(prefix): data[v[skip:]] = variables[v]
    request(method, url, urllib.urlencode(data), verbosity)

def sub(name):
    if '.' in name:
        path = name.split('.')
        var = variables
        for p in path: var = var[p]
        return var
    return variables[name]


def resolve(params):
    return [PATTERN.sub(lambda r: sub(r.group()[2:-1]), x) for x in params]


def call(params):
    name, params = params[0], resolve(params[1:])
    if name not in funcs: die('Unknown function: {}'.format(name))
    func = funcs[name]
    if 'lambda' in func: func['lambda'](*params)
    else:
        if len(func['params']) != len(params): die('Function {} takes {} arguments ({} given)'.format(name, len(func['params']), len(params)))
        for k, v in zip(func['params'], params): variables[k] = v

        for command in func['body']: call(command)


def load_conf(verbose):
    cur_func = '.before'
    num = 1
    conf_dir = os.sep.join((os.path.dirname(os.path.realpath(__file__)), 'crest.conf'))
    for conf_file in sorted(os.listdir(conf_dir)):
        if not conf_file.endswith('.crest'): continue
        with open(os.sep.join((conf_dir, conf_file))) as conf:
            for line in conf:
                line = line.strip()
                if len(line) == 0 or line.startswith('#'): continue
                args = split(line)
                if args[0] == 'function':
                    cur_func = args[1]
                    funcs[cur_func] = {
                        'params': args[2:],
                        'body': []
                    }
                else: funcs[cur_func]['body'].append(args)
                num += 1
        if verbose: output((C_WORD, conf_file), (C_TEXT, ' reloaded'))

def list_commands():
    signatures = [(f, ' '.join(funcs[f]['params'])) for f in sorted(funcs.keys())]
    for name, params in signatures:
        c_name, c_params = (C_WORD, C_TEXT) if 'lambda' in funcs[name] else (C_KEY, C_VALUE)
        output((c_name, name), ' ', (c_params, params), '\n    ', ('info', 'TODO: add description'), '\n')


def basic(func, help):
    return {
        'params': func.func_code.co_varnames,
        'lambda': func
    }

def set_header(header, value): headers[header] = value
def set_variable(name, value):
    if value is None: del variables[name]
    else: variables[name] = value
def drop_header(header): del headers[header]


def ask(var, prompt, hidden):
    variables[var] = (getpass if hidden.lower() == 'hidden' else raw_input)(prompt + ' ')


if __name__ == '__main__':
    VERBOSITY = 'full'
    # url_base = 'http://' + sys.argv[1]

    variables = {
        'response': {}
    }
    headers = {}
    # noinspection PyTypeChecker
    funcs = {
        'echo'          : basic(lambda message: output(('info', message))                  , ''),
        'set'           : basic(lambda name, value=None: set_variable(name, value)         , ''),
        'ask'           : basic(lambda var, prompt='>', hidden='': ask(var, prompt, hidden), ''),

        'get'           : basic(lambda url, verbosity=VERBOSITY: request('GET', url, None, verbosity)                 , ''),
        'post'          : basic(lambda url, body, verbosity=VERBOSITY: request('POST', url, body, verbosity)          , ''),
        'form'          : basic(lambda method, url, prefix, verbosity=VERBOSITY: form(method, url, prefix, verbosity) , ''),
        'delete'        : basic(lambda url, verbosity=VERBOSITY: request('DELETE', url, None, verbosity)              , ''),

        're-extract'    : basic(lambda string, prefix, re_values, re_names=None: re_extract(string, prefix, re_values, re_names), ''),

        'set-header'    : basic(lambda header, value: set_header(header, value)                            , ''),
        'drop-header'   : basic(lambda header: drop_header(header)                                         , ''),

        'reload'        : basic(lambda: load_conf(True)                                                    , ''),
        'list-commands' : basic(lambda: list_commands()                                                    , ''),
        'list-variables': basic(lambda: print_map(variables)                                               , ''),

        '.before': {
            'params': [],
            'body': []
        }
    }

    load_conf(False)

    comp = Completer()
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(comp.complete)
    while True:
        try:
            args = split(raw_input('> '))
            if args:
                call(['.before'])
                call(args)
        except (KeyboardInterrupt, CriticalException): print
        except EOFError:
            print
            exit(0)
        except BaseException:
            output(('error', traceback.format_exc()))
