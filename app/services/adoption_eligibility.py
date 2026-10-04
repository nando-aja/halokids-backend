from datetime import date


MIN_AGE = 30
MAX_AGE = 55
MIN_MARRIAGE_YEARS = 5


def calculate_age(birth_date: date, reference_date: date | None = None) -> int:
    """
    Menghitung usia pemohon secara tepat berdasarkan tanggal lahir.
    """
    if reference_date is None:
        reference_date = date.today()

    age = reference_date.year - birth_date.year

    if (reference_date.month, reference_date.day) < (
        birth_date.month,
        birth_date.day,
    ):
        age -= 1

    return age


def calculate_marriage_duration(
    marriage_date: date,
    reference_date: date | None = None,
) -> tuple[int, int]:
    """
    Menghitung lama pernikahan dalam tahun dan bulan.
    """
    if reference_date is None:
        reference_date = date.today()

    total_months = (
        (reference_date.year - marriage_date.year) * 12
        + (reference_date.month - marriage_date.month)
    )

    if reference_date.day < marriage_date.day:
        total_months -= 1

    if total_months < 0:
        return 0, 0

    years = total_months // 12
    months = total_months % 12

    return years, months


def check_adoption_eligibility(
    birth_date: date,
    marriage_date: date,
    reference_date: date | None = None,
) -> dict:
    """
    Melakukan filter awal kelayakan COTA berdasarkan:
    - usia 30-55 tahun
    - lama pernikahan minimal 5 tahun
    """

    if reference_date is None:
        reference_date = date.today()

    errors: list[str] = []

    # Validasi tanggal dasar
    if birth_date > reference_date:
        errors.append("Tanggal lahir pemohon tidak boleh di masa depan.")

    if marriage_date > reference_date:
        errors.append("Tanggal pernikahan tidak boleh di masa depan.")

    if marriage_date < birth_date:
        errors.append(
            "Tanggal pernikahan tidak boleh lebih awal dari tanggal lahir pemohon."
        )

    age = calculate_age(birth_date, reference_date)

    marriage_years, marriage_months = calculate_marriage_duration(
        marriage_date,
        reference_date,
    )

    # Filter usia
    age_eligible = MIN_AGE <= age <= MAX_AGE

    if not age_eligible:
        errors.append(
            f"Usia pemohon harus berada pada rentang "
            f"{MIN_AGE}-{MAX_AGE} tahun."
        )

    # Filter lama pernikahan
    marriage_eligible = marriage_years >= MIN_MARRIAGE_YEARS

    if not marriage_eligible:
        errors.append(
            f"Lama pernikahan minimal "
            f"{MIN_MARRIAGE_YEARS} tahun."
        )

    eligible = len(errors) == 0

    return {
        "eligible": eligible,
        "usia_pemohon": age,
        "usia_minimal": MIN_AGE,
        "usia_maksimal": MAX_AGE,
        "lama_pernikahan_tahun": marriage_years,
        "lama_pernikahan_bulan": marriage_months,
        "minimal_lama_pernikahan_tahun": MIN_MARRIAGE_YEARS,
        "errors": errors,
    }