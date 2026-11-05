"""Countries for an account's cell phone: ISO code, dialing code and name (es, en).

México first (the league plays there), then the Americas, Spain and the rest by Spanish
name. The account stores the ISO code (several countries share +1) and the number's
digits. Standard library only (users.py imports it, and Kudu runs that).
"""

COUNTRIES = [
    ("MX", "52", "México", "Mexico"),
    ("US", "1", "Estados Unidos", "United States"),
    ("CA", "1", "Canadá", "Canada"),
    ("ES", "34", "España", "Spain"),
    ("AR", "54", "Argentina", "Argentina"),
    ("BO", "591", "Bolivia", "Bolivia"),
    ("BR", "55", "Brasil", "Brazil"),
    ("CL", "56", "Chile", "Chile"),
    ("CO", "57", "Colombia", "Colombia"),
    ("CR", "506", "Costa Rica", "Costa Rica"),
    ("CU", "53", "Cuba", "Cuba"),
    ("EC", "593", "Ecuador", "Ecuador"),
    ("SV", "503", "El Salvador", "El Salvador"),
    ("GT", "502", "Guatemala", "Guatemala"),
    ("HN", "504", "Honduras", "Honduras"),
    ("NI", "505", "Nicaragua", "Nicaragua"),
    ("PA", "507", "Panamá", "Panama"),
    ("PY", "595", "Paraguay", "Paraguay"),
    ("PE", "51", "Perú", "Peru"),
    ("PR", "1", "Puerto Rico", "Puerto Rico"),
    ("DO", "1", "República Dominicana", "Dominican Republic"),
    ("UY", "598", "Uruguay", "Uruguay"),
    ("VE", "58", "Venezuela", "Venezuela"),
    ("DE", "49", "Alemania", "Germany"),
    ("AU", "61", "Australia", "Australia"),
    ("AT", "43", "Austria", "Austria"),
    ("BE", "32", "Bélgica", "Belgium"),
    ("CN", "86", "China", "China"),
    ("KR", "82", "Corea del Sur", "South Korea"),
    ("DK", "45", "Dinamarca", "Denmark"),
    ("AE", "971", "Emiratos Árabes Unidos", "United Arab Emirates"),
    ("FI", "358", "Finlandia", "Finland"),
    ("FR", "33", "Francia", "France"),
    ("GR", "30", "Grecia", "Greece"),
    ("NL", "31", "Países Bajos", "Netherlands"),
    ("IN", "91", "India", "India"),
    ("IE", "353", "Irlanda", "Ireland"),
    ("IL", "972", "Israel", "Israel"),
    ("IT", "39", "Italia", "Italy"),
    ("JP", "81", "Japón", "Japan"),
    ("NO", "47", "Noruega", "Norway"),
    ("NZ", "64", "Nueva Zelanda", "New Zealand"),
    ("PL", "48", "Polonia", "Poland"),
    ("PT", "351", "Portugal", "Portugal"),
    ("GB", "44", "Reino Unido", "United Kingdom"),
    ("CZ", "420", "República Checa", "Czech Republic"),
    ("SE", "46", "Suecia", "Sweden"),
    ("CH", "41", "Suiza", "Switzerland"),
    ("ZA", "27", "Sudáfrica", "South Africa"),
    ("TR", "90", "Turquía", "Turkey"),
]
DEFAULT = "MX"
DIAL = {code: dial for code, dial, _, _ in COUNTRIES}


def phone_display(country, phone):
    """'+52 5512345678', or '' when there's no phone."""
    return f"+{DIAL.get(country, '')} {phone}" if phone else ""


def phone_link(country, phone):
    """The tel: link, e.g. 'tel:+525512345678'."""
    return f"tel:+{DIAL.get(country, '')}{phone}" if phone else ""
