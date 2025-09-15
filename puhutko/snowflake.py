from snowflake import SnowflakeGenerator


generator = SnowflakeGenerator(1)


def snowflake() -> int:
    return next(generator) or 0
