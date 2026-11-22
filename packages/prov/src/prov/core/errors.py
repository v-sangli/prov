"""Every error prov raises on purpose is a ProvError; the CLI prints it as `prov: <message>`."""


class ProvError(Exception):
    pass


class ConfigError(ProvError):
    pass


class IdError(ProvError, ValueError):
    pass


class StoreError(ProvError):
    pass


class RegistryLocked(ProvError):
    pass


class RunError(ProvError):
    pass


class AliasError(ProvError):
    pass


class SnapshotError(ProvError):
    pass


class DatasetError(ProvError):
    pass


class RerunError(ProvError):
    pass


class JournalError(ProvError):
    pass


class SiteError(ProvError):
    pass
