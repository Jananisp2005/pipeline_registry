class PipelineServiceError(Exception):
    pass


class PipelineNotFoundError(Exception):
    pass


class DuplicatePipelineError(Exception):
    pass


class SchemaNotFoundError(Exception):
    pass


class RegistryUnavailableServiceError(Exception):
    pass