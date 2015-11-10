#!/usr/bin/python2
import json, os, re, readline, sys, traceback, urllib2

PATTERN = re.compile('\${.*?}')
LAMBDA = type(lambda: 0)
RE_SPACE = re.compile('.*\s+$', re.M)


class CriticalException(BaseException): pass


class Completer(object):
    def complete(self, text, state):
        buf = readline.get_line_buffer()
        line = readline.get_line_buffer().split()
        # show all commands
        if not line:
            return [c + ' ' for c in funcs.keys()][state]
        # account for last argument ending in a space
        if RE_SPACE.match(buf): line.append('')
        # resolve command to the implementation function
        cmd = line[0].strip()
        if cmd in funcs.keys():
            impl = getattr(self, 'complete_%s' % cmd)
            args = line[1:]
            if args: return (impl(args) + [None])[state]
            return [cmd + ' '][state]
        results = [c + ' ' for c in funcs.keys() if c.startswith(cmd)] + [None]
        return results[state]


def colored(color, message):
    color_table = {
        'error': (255, 107, 104),
        'info': (83, 148, 236),
        'response': (0, 127, 127),
        'warning': (205, 205, 0)
    }
    csi = '\x1B['
    print ''.join((csi, '38;2;{};{};{}m'.format(*color_table[color]), message, csi, '0m'))


def die(message):
    colored('error', 'CRITICAL ERROR:\n  {}'.format(message))
    raise CriticalException


def split(string):
    return [x[1:-1] if x.startswith("'") and x.endswith("'") else x for x in re.split("( |'.*?')", string) if x.strip()]


def request(method, url, data=None):
    colored('info', '{} {}'.format(method, url_base + url))
    print
    if data: headers['Content-Length'] = len(data)
    elif 'Content-Length' in headers: del headers['Content-Length']

    req = urllib2.Request(url_base + url, data, headers)
    if headers:
        l = max([len(h) for h in headers.keys()])
        for header, value in headers.iteritems():
            colored('info', '{1:{0}} : {2}'.format(l, header, value))
        print
    if data:
        colored('info', data)
        print

    variables['response'] = json.loads(urllib2.urlopen(req).read())
    colored('response', json.dumps(variables['response'], sort_keys=True, indent=2, separators=(',', ':')))
    print


def set_header(header, value): headers[header] = value


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
    if isinstance(func, LAMBDA): func(*params)
    else:
        if len(func['params']) != len(params): die('Function {} requires {} arguments, {} given'.format(name, len(func['params']), len(params)))
        for k, v in zip(func['params'], params): variables[k] = v

        for command in func['body']: call(command)


def load_conf():
    cur_func = None
    num = 1
    with open(os.sep.join((os.path.dirname(os.path.realpath(__file__)), 'crest.conf'))) as conf:
        for line in conf:
            line = line.strip()
            if len(line) == 0 or line.startswith('#'): continue
            args = split(line)
            if cur_func is None and args[0] != 'function': die('Line {}: commands outside function body'.format(num))
            if args[0] == 'function':
                cur_func = args[1]
                funcs[cur_func] = {
                    'params': args[2:],
                    'body': []
                }
            else: funcs[cur_func]['body'].append(args)
            num += 1


if __name__ == '__main__':
    variables = {}
    headers = {}

    url_base = 'http://' + sys.argv[1]
    funcs = {
        'get': lambda url: request('GET', url),
        'post': lambda url, data: request('POST', url, data),
        'set-header': lambda header, value: set_header(header, value),
        'reload': lambda: load_conf()
    }

    load_conf()

    comp = Completer()
    readline.set_completer_delims(' \t\n;')
    readline.parse_and_bind("tab: complete")
    readline.set_completer(comp.complete)
    while True:
        try:
            args = split(raw_input('> '))
            if args: call(args)
        except (KeyboardInterrupt, CriticalException): print
        except EOFError:
            print
            exit(0)
        except BaseException:
            colored('error', traceback.format_exc())
