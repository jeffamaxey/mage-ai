def number_string(version: int, number_of_numbers: int = 20) -> str:
    version_string = str(version)
    for _ in range(number_of_numbers - len(version_string)):
        version_string = f'0{version_string}'

    return version_string
