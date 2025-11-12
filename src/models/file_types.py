from enum import Enum
from typing import Dict, List


class FileType(Enum):
    PDF = "pdf"
    TEXT = "text"


class FileExtensions:
    SUPPORTED_EXTENSIONS: Dict[str, FileType] = {
        '.pdf': FileType.PDF,
        '.txt': FileType.TEXT,
        '.md': FileType.TEXT,
        '.csv': FileType.TEXT,
        '.json': FileType.TEXT,
        '.xml': FileType.TEXT,
        '.html': FileType.TEXT,
        '.htm': FileType.TEXT,
    }

    @classmethod
    def get_file_type(cls, extension: str) -> FileType:
        extension_lower = extension.lower()
        if extension_lower not in cls.SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError(f"Unsupported file extension: {extension}")
        return cls.SUPPORTED_EXTENSIONS[extension_lower]

    @classmethod
    def is_supported(cls, extension: str) -> bool:
        return extension.lower() in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        return list(cls.SUPPORTED_EXTENSIONS.keys())


class UnsupportedFileTypeError(Exception):
    pass