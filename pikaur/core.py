import os
import shutil
import subprocess
import enum
import codecs
from typing import Dict, Any, List, Iterable, Tuple, Union, Callable


NOT_FOUND_ATOM = object()


class PackageSource(enum.Enum):
    REPO = enum.auto()
    AUR = enum.auto()
    LOCAL = enum.auto()


def interactive_spawn(cmd: List[str], **kwargs) -> subprocess.Popen:
    process = subprocess.Popen(cmd, **kwargs)
    process.communicate()
    return process


def running_as_root() -> bool:
    return os.geteuid() == 0


def isolate_root_cmd(cmd: List[str], cwd=None) -> List[str]:
    if not running_as_root():
        return cmd
    base_root_isolator = ['systemd-run', '--pipe', '--wait',
                          '-p', 'DynamicUser=yes',
                          '-p', 'CacheDirectory=pikaur']
    if cwd is not None:
        base_root_isolator += ['-p', 'WorkingDirectory=' + cwd]
    return base_root_isolator + cmd


class DataType():

    def __init__(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __setattr__(self, key: str, value: Any) -> None:
        if getattr(self, key, NOT_FOUND_ATOM) is NOT_FOUND_ATOM:
            raise TypeError(
                f"'{self.__class__.__name__}' does "
                f"not have attribute '{key}'"
            )
        super().__setattr__(key, value)


def open_file(file_path: str, mode='r', encoding='utf-8', **kwargs):
    return codecs.open(file_path, mode, encoding=encoding, **kwargs)


CONFIG_VALUE_TYPE = Union[str, List[str]]
CONFIG_FORMAT = Dict[str, CONFIG_VALUE_TYPE]


class ConfigReader():

    comment_prefixes = ('#', ';')

    _cached_config: Dict[str, CONFIG_FORMAT] = None
    default_config_path: str = None  # noqa
    list_fields: List[str] = []
    ignored_fields: List[str] = []

    @classmethod
    def _parse_line(cls, line: str) -> Tuple[str, CONFIG_VALUE_TYPE]:
        blank = (None, None, )
        if line.startswith(' '):
            return blank
        if '=' not in line:
            return blank
        line = line.strip()
        for comment_prefix in cls.comment_prefixes:
            line, *_comments = line.split(comment_prefix)

        key, *values = line.split('=')
        value = '='.join(values)
        key = key.strip()
        value = value.strip()

        if key in cls.ignored_fields:
            return blank

        if value:
            value = value.strip('"').strip("'")
        else:
            return key, value

        if key in cls.list_fields:
            list_value = value.split()
            return key, list_value

        return key, value

    @classmethod
    def get_config(cls, config_path: str = None) -> CONFIG_FORMAT:
        config_path = config_path or cls.default_config_path
        if not cls._cached_config:
            cls._cached_config = {}
        if not cls._cached_config.get(config_path):
            with open_file(config_path) as config_file:
                cls._cached_config[config_path] = {
                    key: value
                    for key, value in [
                        cls._parse_line(line)
                        for line in config_file.readlines()
                    ] if key
                }
        return cls._cached_config[config_path]

    @classmethod
    def get(cls, key: str, fallback: Any = None, config_path: str = None) -> Any:
        return cls.get_config(config_path=config_path).get(key) or fallback


def remove_dir(dir_path: str) -> None:
    try:
        shutil.rmtree(dir_path)
    except PermissionError:
        interactive_spawn(['sudo', 'rm', '-rf', dir_path])


def get_chunks(iterable: Iterable[Any], chunk_size: int) -> Iterable[List[Any]]:
    result = []
    index = 0
    for item in iterable:
        result.append(item)
        index += 1
        if index == chunk_size:
            yield result
            result = []
            index = 0
    if result:
        yield result


def return_exception(fun: Callable) -> Callable:
    def decorator(*args, **kwargs):
        try:
            return fun(*args, **kwargs)
        except Exception as exc:
            return exc
    return decorator
