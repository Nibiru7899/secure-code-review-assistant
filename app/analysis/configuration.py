"""Capture only analysis options; compilation database commands never execute."""
import json
from pathlib import Path, PurePosixPath
import re
import shlex

from app.security.permissions import relative_path

STANDARDS = {'c89', 'c99', 'c11', 'c++03', 'c++11', 'c++14', 'c++17', 'c++20'}
PLATFORMS = {'unix32', 'unix64', 'win32A', 'win32W', 'win64'}


def capture_configuration(config, source, scope):
    if config is None:
        return None
    if not isinstance(config, dict) or set(config) - {'include_paths', 'defines', 'standard', 'platform', 'compile_commands'}:
        raise ValueError('Unsupported project analysis configuration fields')
    if any(not isinstance(config.get(k, []), list) for k in ('include_paths', 'defines')):
        raise ValueError('Include paths and defines must be lists')
    includes, defines = list(config.get('include_paths', [])), list(config.get('defines', []))
    standards = set([config['standard']] if config.get('standard') else [])
    limitations = []
    def captured_path(value, base='.', file=False):
        if not isinstance(value, str) or not value or '\x00' in value:
            raise ValueError('Invalid analysis configuration path')
        value = value.replace('\\', '/')
        absolute = Path(value)
        if absolute.is_absolute():
            try: value = absolute.resolve().relative_to(scope.root).as_posix()
            except ValueError: raise ValueError('Analysis configuration path outside authorized repository') from None
        elif base != '.':
            value = str(PurePosixPath(base) / value)
        if value == '.':
            if file: raise ValueError('Compilation file must be captured source')
            return value
        value = relative_path(value)
        if not scope.allows(value):
            raise ValueError('Analysis configuration path outside authorized scope')
        if file and value not in source:
            raise ValueError('Compilation file absent from captured source')
        if not file and not any(p.startswith(value.rstrip('/') + '/') for p in source):
            raise ValueError('Include directory absent from captured source')
        return value
    database = config.get('compile_commands')
    if database is not None:
        if not isinstance(database, str) or len(database.encode()) > 65536:
            raise ValueError('Compilation database must be bounded imported JSON text')
        entries = json.loads(database)
        if not isinstance(entries, list) or len(entries) > 1000:
            raise ValueError('Invalid compilation database entries')
        for entry in entries:
            if not isinstance(entry, dict): raise ValueError('Invalid compilation entry')
            directory = captured_path(entry.get('directory', '.'))
            captured_path(entry.get('file', ''), directory, file=True)
            args = entry.get('arguments')
            if args is None:
                # A command is parsed only for whitelisted analysis flags. Shell
                # operators and executable names have no effect and never run.
                command = entry.get('command', '')
                if not isinstance(command, str): raise ValueError('Invalid compilation command text')
                args = shlex.split(command, posix=True)
                limitations.append('Compilation command parsed as inert text; unsupported arguments ignored, no commands executed')
            if not isinstance(args, list) or len(args) > 300 or any(not isinstance(a, str) for a in args):
                raise ValueError('Invalid compilation argument list')
            i = 0
            while i < len(args):
                argument = args[i]
                if argument in ('-I', '-D'):
                    i += 1
                    if i >= len(args): raise ValueError('Missing analysis flag value')
                    argument += args[i]
                if argument.startswith('-I'):
                    includes.append(captured_path(argument[2:], directory))
                elif argument.startswith('-D'):
                    defines.append(argument[2:])
                elif argument.startswith('-std='):
                    standards.add(argument[5:])
                elif argument.startswith('-'):
                    limitations.append('Unsupported compilation arguments ignored; captured analysis configuration is partial')
                i += 1
    if len(includes) > 20 or len(defines) > 50 or len(standards) > 1:
        raise ValueError('Project configuration too large or has conflicting standards')
    includes = sorted({captured_path(p) for p in includes})
    if any(not isinstance(d, str) or not re.fullmatch(r'[A-Za-z_]\w*(?:=[A-Za-z0-9_+-]+)?', d) or len(d) > 150 for d in defines):
        raise ValueError('Only simple literal macro definitions are supported')
    if not standards <= STANDARDS or config.get('platform') not in (None, *PLATFORMS):
        raise ValueError('Unsupported analysis standard/platform')
    return {'include_paths': includes, 'defines': sorted(set(defines)), 'standard': next(iter(standards), None),
            'platform': config.get('platform'), 'limitations': sorted(set(limitations)),
            'provenance': 'User-supplied analysis configuration captured with authorized source; not independently verified build provenance'}


def arguments(config):
    if config is None:
        return ['--std=c++17', '--std=c11', '-Iinclude']
    result = ['-I' + path for path in config['include_paths']] + ['-D' + value for value in config['defines']]
    result += ['--std=' + config['standard']] if config['standard'] else ['--std=c++17', '--std=c11']
    if config['platform']: result.append('--platform=' + config['platform'])
    return result
