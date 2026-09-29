# ruff: noqa: E501 - one row per line reads best as a table
"""Hand-written UK battery rows (plan step 8). ``build_uk.py`` merges them with the sampled rows.

Every label comes from grammar.md and the plan's stated expectations, never from a router
run. ``build_uk.py`` checks each label's facts against the full index before writing:
expected coordinates exist, ``absent:`` coordinates in ``notes`` do not, and invented titles
are in neither the index nor the catalogue.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# fmt: off

B: Final = "ROUTE_BOUNDED"
A: Final = "ROUTE_AMBIGUOUS"
I: Final = "EPISTEMIC_ABSTENTION_INSTRUMENT_NOT_FOUND"  # noqa: E741 - grammar.md status letters
P: Final = "EPISTEMIC_ABSTENTION_PROVISION_NOT_FOUND"
O: Final = "ROUTE_OUT_OF_COVERAGE"  # noqa: E741
U: Final = "ROUTE_UNRESOLVED"

ERA: Final = "uk/ukpga/1996/18"
ERA25: Final = "uk/ukpga/2025/36"
EQA06: Final = "uk/ukpga/2006/3"
WTR99: Final = "uk/uksi/1999/3372"
ETA: Final = "uk/ukpga/1996/17"
ARB: Final = "uk/ukpga/1996/23"
CA06: Final = "uk/ukpga/2006/46"
EQA: Final = "uk/ukpga/2010/15"
FSMA: Final = "uk/ukpga/2000/8"
TULRCA: Final = "uk/ukpga/1992/52"
THEFT: Final = "uk/ukpga/1968/60"
FRAUD: Final = "uk/ukpga/2006/35"
BRIBERY: Final = "uk/ukpga/2010/23"
HRA: Final = "uk/ukpga/1998/42"
DPA18: Final = "uk/ukpga/2018/12"
HSWA: Final = "uk/ukpga/1974/37"
IA86: Final = "uk/ukpga/1986/45"
PACE: Final = "uk/ukpga/1984/60"
POCA: Final = "uk/ukpga/2002/29"
CRA15: Final = "uk/ukpga/2015/15"
SCA81: Final = "uk/ukpga/1981/54"
CJA03: Final = "uk/ukpga/2003/44"
CHILDREN: Final = "uk/ukpga/1989/41"
MDA: Final = "uk/ukpga/1971/38"
MCA05: Final = "uk/ukpga/2005/9"
FOIA: Final = "uk/ukpga/2000/36"
LIMITATION: Final = "uk/ukpga/1980/58"
EPA90: Final = "uk/ukpga/1990/43"
TCPA90: Final = "uk/ukpga/1990/8"
RTA88: Final = "uk/ukpga/1988/52"
SGA79: Final = "uk/ukpga/1979/54"
CMA90: Final = "uk/ukpga/1990/18"
PHA97: Final = "uk/ukpga/1997/40"
LDEDCA: Final = "uk/ukpga/2009/20"
OAPA: Final = "uk/ukpga/Vict/24-25/100"
PARTNERSHIP: Final = "uk/ukpga/Vict/53-54/39"
BILLS: Final = "uk/ukpga/Vict/45-46/61"
LPA25: Final = "uk/ukpga/Geo5/15-16/20"
LTA54: Final = "uk/ukpga/Eliz2/2-3/56"
SI_2011: Final = "uk/uksi/2011/3006"
SI_2026: Final = "uk/uksi/2026/310"
TUPE: Final = "uk/uksi/2006/246"
WTR: Final = "uk/uksi/1998/1833"
NMW: Final = "uk/uksi/2015/621"
CPR: Final = "uk/uksi/1998/3132"
MHSW: Final = "uk/uksi/1999/3242"
SUGAR_BEET: Final = "uk/uksi/1981/292"
AIR_NAV_A: Final = "uk/uksi/1976/783"
AIR_NAV_B: Final = "uk/uksi/1976/1783"


@dataclass(frozen=True, slots=True)
class Hand:
    """A hand-written row before it gets its id. ``forms`` are grammar.md row ids."""

    query: str
    status: str
    coordinates: tuple[str, ...] = ()
    forms: tuple[str, ...] = ()
    notes: str = ""
    context: tuple[str, ...] | None = None
    absent_title: bool = False
    """Invented instrument: ``build_uk.py`` checks the title is in neither index nor catalogue."""


def h(
    query: str,
    status: str,
    *coordinates: str,
    forms: tuple[str, ...] = (),
    notes: str = "",
    context: tuple[str, ...] | None = None,
    absent_title: bool = False,
) -> Hand:
    return Hand(query, status, coordinates, forms, notes, context, absent_title)


# ---------------------------------------------------------------- collision (02 §8)
# The same provision number in different instruments. A collision is a bound result in
# the wrong instrument.

COLLISION: Final = [
    h("section 124 of the Employment Rights Act 1996", B, f"{ERA}/s124", forms=("UK-P-02", "UK-I-01", "UK-L-01")),
    h("Employment Rights Act 1996, s. 124", B, f"{ERA}/s124", forms=("UK-P-01", "UK-L-01")),
    h("s.124 ERA 1996", B, f"{ERA}/s124", forms=("UK-P-01", "UK-I-05", "UK-L-01")),
    h("ERA 1996 s124", B, f"{ERA}/s124", forms=("UK-P-01", "UK-I-05")),
    h("compensation limit under Employment Rights Act 1996 section 124", B, f"{ERA}/s124", forms=("UK-P-02", "UK-I-01")),
    h("What is the cap in s 124 of the ERA '96?", B, f"{ERA}/s124", forms=("UK-P-01", "UK-I-05")),
    h("section 124 of the Companies Act 2006", B, f"{CA06}/s124", forms=("UK-P-02", "UK-I-01")),
    h("Companies Act 2006, s.124", B, f"{CA06}/s124", forms=("UK-P-01",)),
    h("CA 2006 s. 124", B, f"{CA06}/s124", forms=("UK-I-05",)),
    h("inspection under Companies Act 2006 section 124", B, f"{CA06}/s124", forms=("UK-P-02",)),
    h("section 124 of the Equality Act 2010", B, f"{EQA}/s124", forms=("UK-P-02",)),
    h("remedies under Equality Act 2010 section 124", B, f"{EQA}/s124", forms=("UK-P-02",)),
    h("EqA 2010, s 124", B, f"{EQA}/s124", forms=("UK-I-05", "UK-P-01")),
    h("EA 2010 s.124", B, f"{EQA}/s124", forms=("UK-I-05",), notes="curated alias beats the generated acronym (decision 18)"),
    h("section 124 of the Financial Services and Markets Act 2000", B, f"{FSMA}/s124"),
    h("FSMA 2000 s.124", B, f"{FSMA}/s124", forms=("UK-I-05",)),
    h("section 124 of the Trade Union and Labour Relations (Consolidation) Act 1992", B, f"{TULRCA}/s124", forms=("UK-I-01",)),
    h("TULRCA s.124", B, f"{TULRCA}/s124", forms=("UK-I-05",)),
    h("ERA 1996 s.124 and Companies Act 2006 s.124", B, f"{ERA}/s124", f"{CA06}/s124", forms=("UK-C-09",)),
    h("s. 124 of the Equality Act 2010, not s. 124 of the Employment Rights Act 1996", B, f"{EQA}/s124", forms=("UK-L-04",), notes="the negated ERA s.124 is never bound"),
    h("section 1 of the Theft Act 1968", B, f"{THEFT}/s1"),
    h("section 1 of the Fraud Act 2006", B, f"{FRAUD}/s1"),
    h("Bribery Act 2010, section 1", B, f"{BRIBERY}/s1"),
    h("Theft Act 1968 s.1 and Fraud Act 2006 s.1", B, f"{THEFT}/s1", f"{FRAUD}/s1", forms=("UK-C-09",)),
    h("section 3 of the Human Rights Act 1998", B, f"{HRA}/s3"),
    h("HRA 1998 s 3", B, f"{HRA}/s3", forms=("UK-I-05",)),
    h("section 3 of the Theft Act 1968", B, f"{THEFT}/s3"),
    h("section 98 of the Employment Rights Act 1996", B, f"{ERA}/s98"),
    h("section 98 of the Companies Act 2006", B, f"{CA06}/s98"),
    h("regulation 4 of the Working Time Regulations 1998", B, f"{WTR}/reg4", forms=("UK-P-10",)),
    h("regulation 4 of the Transfer of Undertakings (Protection of Employment) Regulations 2006", B, f"{TUPE}/reg4", forms=("UK-P-10",)),
    h("article 3 of the Employment Rights (Increase of Limits) Order 2011", B, f"{SI_2011}/art3", forms=("UK-P-11", "UK-I-13")),
    h("article 2 of S.I. 2026/310", B, f"{SI_2026}/art2", forms=("UK-P-11", "UK-I-09")),
    h("section 2 of the Health and Safety at Work etc. Act 1974", B, f"{HSWA}/s2", forms=("UK-I-25",)),
    h("section 2 of the Theft Act 1968", B, f"{THEFT}/s2"),
    h("section 18 of the Offences against the Person Act 1861", B, f"{OAPA}/s18", forms=("UK-I-25",)),
    h("section 18 of the Theft Act 1968", B, f"{THEFT}/s18"),
    h("section 170 of the Data Protection Act 2018", B, f"{DPA18}/s170"),
    h("section 37 of the Senior Courts Act 1981", B, f"{SCA81}/s37"),
    h("section 37 of the Supreme Court Act 1981", B, f"{SCA81}/s37", forms=("UK-I-27",), notes="former title of the Senior Courts Act 1981"),
]

# ---------------------------------------------------------------- misroute, hand slice
# Informal queries a naive router could bind to the wrong instrument.

MISROUTE: Final = [
    h("the ERA 1996 s.124 cap, as opposed to s.124 of the Companies Act 2006", B, f"{ERA}/s124", f"{CA06}/s124"),
    h("Under s.124 (Employment Rights Act 1996) the award is capped", B, f"{ERA}/s124"),
    h("Employment Tribunals Act 1996 s. 4", B, f"{ETA}/s4", notes="not the Employment Rights Act 1996"),
    h("Industrial Tribunals Act 1996, s. 4", B, f"{ETA}/s4", forms=("UK-I-27",), notes="former title of the Employment Tribunals Act 1996"),
    h("Arbitration Act 1996 s. 68", B, f"{ARB}/s68"),
    h("s. 68 of the 1996 Arbitration Act", B, f"{ARB}/s68", forms=("UK-I-03",)),
    h("Theft Act 1968 (c. 60), s. 1", B, f"{THEFT}/s1", forms=("UK-I-21",)),
    h("1968 c. 60, s. 12", B, f"{THEFT}/s12", forms=("UK-I-08",)),
    h("c. 60 of 1968, section 12", B, f"{THEFT}/s12", forms=("UK-I-08",)),
    h("section 12 of the Theft Act 1968 and section 12 of the Fraud Act 2006", B, f"{THEFT}/s12", f"{FRAUD}/s12"),
    h("Employment Rights Act 1996 (c. 18), ss. 94, 95", B, f"{ERA}/s94", f"{ERA}/s95", forms=("UK-P-19", "UK-I-21")),
    h("sections 94, 95 and 98 of the Employment Rights Act 1996", B, f"{ERA}/s94", f"{ERA}/s95", f"{ERA}/s98", forms=("UK-P-06",)),
    h("S.I. 2011/3006, art. 3 and 1996 c. 18", B, f"{SI_2011}/art3", ERA, forms=("UK-P-06", "UK-I-08")),
    h("S.I. 2011/3006 (article 3), 2026/310 (article 2)", B, f"{SI_2011}/art3", f"{SI_2026}/art2", forms=("UK-I-22",)),
    h("S.I. 2011/3006, article 3, 2026/310, article 2", B, f"{SI_2011}/art3", f"{SI_2026}/art2", forms=("UK-I-22",)),
    h("The Employment Rights (Increase of Limits) Order 2011 (S.I. 2011/3006)", B, SI_2011, forms=("UK-I-30",)),
    h("The Employment Rights (Increase of Limits) Order 2011, S.I. 2026/310", B, SI_2011, SI_2026, forms=("UK-I-30",), notes="no brackets: a list of two"),
    h("S.I. 2011/3006 (S. 1)", B, SI_2011, forms=("UK-I-29",), notes="(S. 1) is a series note, never section 1"),
    h("S.I. 2011/3006 (C. 5) and 2026/310", B, SI_2011, SI_2026, forms=("UK-I-22", "UK-I-29")),
    h("regulation 3 of the Transfer of Undertakings (Protection of Employment) Regulations 2006 and 2006 c. 46", B, CA06, f"{TUPE}/reg3", forms=("UK-P-06",), notes="a year starting an official number ends the provision list"),
    h("Law of Property Act 1925, s. 1", B, f"{LPA25}/s1"),
    h("1925 c. 20, s. 1", B, f"{LPA25}/s1", forms=("UK-I-23",)),
    h("15 & 16 Geo. 5 c. 20, s. 1", B, f"{LPA25}/s1", forms=("UK-I-10",)),
    h("Landlord and Tenant Act 1954, s. 24", B, f"{LTA54}/s24"),
    h("2 & 3 Eliz. 2 c. 56, section 24", B, f"{LTA54}/s24", forms=("UK-I-10",)),
    h("words omitted by virtue of Theft Act 1968 (c. 60)", B, THEFT, forms=("UK-I-26", "UK-I-21")),
    h("Local Democracy, Economic Development and Construction Act 2009, s. 1", B, f"{LDEDCA}/s1", forms=("UK-I-24",)),
    h("the Health and Safety at Work etc. Act 1974 and the Management of Health and Safety at Work Regulations 1999", B, HSWA, MHSW, forms=("UK-I-25", "UK-C-09")),
    h("Partnership Act 1890, s. 1", B, f"{PARTNERSHIP}/s1"),
    h("Bills of Exchange Act 1882, s. 3", B, f"{BILLS}/s3"),
]

# ---------------------------------------------------------------- false abstention, hand slice
# Forms that must bind (grammar.md 4.1 and 4.2). The sampled slice is built in build_uk.py.

FALSE_ABSTENTION: Final = [
    h("s.124 of the Employment Rights Act 1996", B, f"{ERA}/s124", forms=("UK-P-01",)),
    h("s 124 Employment Rights Act 1996", B, f"{ERA}/s124", forms=("UK-P-01",)),
    h("sec. 124 of the Employment Rights Act 1996", B, f"{ERA}/s124", forms=("UK-P-02", "UK-R-02")),
    h("sect. 124 of the Employment Rights Act 1996", B, f"{ERA}/s124", forms=("UK-P-02", "UK-R-02")),
    h("§ 124 of the Employment Rights Act 1996", B, f"{ERA}/s124", forms=("UK-P-02", "UK-R-02")),
    h("s.124(1ZA)(a) of the Employment Rights Act 1996", B, f"{ERA}/s124/1ZA/a", forms=("UK-P-03",)),
    h("section 124(1ZA)(a) ERA 1996", B, f"{ERA}/s124/1ZA/a", forms=("UK-P-03",)),
    h("subsection (1ZA) of section 124 of the Employment Rights Act 1996", B, f"{ERA}/s124/1ZA", forms=("UK-P-04",)),
    h("ss.94-95 of the Employment Rights Act 1996", B, f"{ERA}/s94", f"{ERA}/s95", forms=("UK-P-05",)),
    h("sections 94 to 95 of the Employment Rights Act 1996", B, f"{ERA}/s94", f"{ERA}/s95", forms=("UK-P-05",)),
    h("ss. 94 & 98 of the Employment Rights Act 1996", B, f"{ERA}/s94", f"{ERA}/s98", forms=("UK-P-06",)),
    h("Schedule 1, paragraph 1 to the Theft Act 1968", B, f"{THEFT}/sch1/para1", forms=("UK-P-08",)),
    h("para 1 of Schedule 1 to the Theft Act 1968", B, f"{THEFT}/sch1/para1", forms=("UK-P-08",)),
    h("TULRCA 1992 Sch. A1 para. 1", B, f"{TULRCA}/schA1/para1", forms=("UK-P-08a",)),
    h("Insolvency Act 1986, Schedule B1 paragraph 14", B, f"{IA86}/schB1/para14", forms=("UK-P-08a",)),
    h("the Schedule, para 3 to the Property Misdescriptions Act 1991", B, "uk/ukpga/1991/29/sch/para3", forms=("UK-P-09",), notes="sole unnumbered Schedule"),
    h("Property Misdescriptions Act 1991, Sch. para 3", B, "uk/ukpga/1991/29/sch/para3", forms=("UK-P-09",)),
    h("Part 2, Chapter 1 of the Data Protection Act 2018", B, f"{DPA18}/pt2/ch1", forms=("UK-P-14",)),
    h("Companies Act 2006 Pt 10 Ch 2", B, f"{CA06}/pt10/ch2", forms=("UK-P-14",)),
    h("regulation 4(1) of the Working Time Regulations 1998", B, f"{WTR}/reg4/1", forms=("UK-P-10",)),
    h("reg 4(1) Working Time Regulations 1998", B, f"{WTR}/reg4/1", forms=("UK-P-10",)),
    h("Employment Rights (Increase of Limits) Order 2011, art. 4", B, f"{SI_2011}/art4", forms=("UK-P-11",)),
    h("r. 3.1 of the Civil Procedure Rules 1998", B, f"{CPR}/rule3.1", forms=("UK-P-12",)),
    h("CPR rule 3.1(2)", B, f"{CPR}/rule3.1/2", forms=("UK-P-12", "UK-I-05")),
    h("secton 124 of the Employment Rights Act 1996", B, f"{ERA}/s124", forms=("UK-P-16",)),
    h("sectoin 124 of the Employment Rights Act 1996", B, f"{ERA}/s124", forms=("UK-P-16",)),
    h("regualtion 4 of the Working Time Regulations 1998", B, f"{WTR}/reg4", forms=("UK-P-16",)),
    h("artcle 3 of the Employment Rights (Increase of Limits) Order 2011", B, f"{SI_2011}/art3", forms=("UK-P-16",)),
    h("Employment Rights Act 1996", B, ERA, forms=("UK-I-01",)),
    h("employment rights act 1996", B, ERA, forms=("UK-I-02",)),
    h("EMPLOYMENT RIGHTS ACT 1996", B, ERA, forms=("UK-I-02", "UK-C-15")),
    h("the 1996 Employment Rights Act", B, ERA, forms=("UK-I-03",)),
    h("Employment Rights Act of 1996", B, ERA, forms=("UK-I-04",)),
    h("Employment Rights Act (1996)", B, ERA, forms=("UK-I-04",)),
    h("ERA 96", B, ERA, forms=("UK-I-05",)),
    h("employment rights 1996", B, ERA, forms=("UK-I-06",)),
    h("1996 c. 18", B, ERA, forms=("UK-I-08",)),
    h("1996 c 18", B, ERA, forms=("UK-I-08",)),
    h("SI 2011/3006", B, SI_2011, forms=("UK-I-09",)),
    h("S.I. 2011 No. 3006", B, SI_2011, forms=("UK-I-09",)),
    h("2011 No. 3006", B, SI_2011, forms=("UK-I-09",)),
    h("S.I. 2011/ 3006", B, SI_2011, forms=("UK-I-09",)),
    h("S.I.s 2011/3006 and 2026/310", B, SI_2011, SI_2026, forms=("UK-I-09", "UK-I-22")),
    h("8 & 9 Eliz. 2 c. 69", B, "uk/ukpga/Eliz2/8-9/69", forms=("UK-I-10",)),
    h("Employment Rights Act 1996 ... section 124 of the 1996 Act", B, f"{ERA}/s124", forms=("UK-I-11",)),
    h("the Theft Act 1968, and s. 1 of that Act", B, f"{THEFT}/s1", forms=("UK-I-12",)),
    h("The Employment Rights (Increase of Limits) Order 2011", B, SI_2011, forms=("UK-I-13", "UK-C-02"), notes="repealed: bound with repealed=True"),
    h("Employment Rights (Increase of Limits) Order 2011", B, SI_2011, forms=("UK-I-13",)),
    h("Supreme Court Act 1981", B, SCA81, forms=("UK-I-27",)),
    h("PACE 1984", B, PACE, forms=("UK-I-28",)),
    h("POCA 2002", B, POCA, forms=("UK-I-28",)),
    h("OAPA 1861 s. 18", B, f"{OAPA}/s18", forms=("UK-I-05",)),
    h("FA 2022", B, "uk/ukpga/2022/3", forms=("UK-I-28",), notes="Finance Act 2022; no other 2022 Act has these initials"),
    h("tcga 1992", B, "uk/ukpga/1992/12", forms=("UK-I-28",)),
    h("Employment Rights Act 1996 (c. 18)", B, ERA, forms=("UK-I-21",)),
    h("Theft Act 1968 c. 60", B, THEFT, forms=("UK-I-21",)),
    h("S.I. 1980 No. 765 and 1988 No. 1640", B, "uk/uksi/1980/765", "uk/uksi/1988/1640", forms=("UK-I-22",)),
    h("section 1 of the Theft Act 1968 (E.W.)", B, f"{THEFT}/s1", forms=("UK-L-06",)),
    h("section 124 of the Employment Rights Act 1996, as amended on 1.3.2007", B, f"{ERA}/s124", forms=("UK-L-05",)),
    h("Employment Rights Act 1996 s. 124 (20.7.1998)", B, f"{ERA}/s124", forms=("UK-L-05",)),
    h("section 124 of the Employment Rights Act 1996 from 6th April 2020", B, f"{ERA}/s124", forms=("UK-L-05",)),
    h("section 124 of the Employment Rights Act 1996 as it stood on 1 April 2012", B, f"{ERA}/s124", forms=("UK-L-07", "UK-C-08")),
    h("section 1 of the Theft Act 1968 as enacted", B, f"{THEFT}/s1", forms=("UK-L-07", "UK-C-08")),
    h("the original version of section 1 of the Theft Act 1968", B, f"{THEFT}/s1", forms=("UK-C-08",)),
    h("Under the Theft Act 1968, what does section 1 say?", B, f"{THEFT}/s1", forms=("UK-L-02", "UK-C-20")),
    h("the \u201cEmployment Rights Act 1996\u201d, s. 124", B, f"{ERA}/s124", forms=("UK-C-13", "UK-R-03")),
    h("sections 94\u201395 of the Employment Rights Act 1996", B, f"{ERA}/s94", f"{ERA}/s95", forms=("UK-C-13", "UK-R-03")),
    h("Employment Rights Act \uff11\uff19\uff19\uff16 section \uff11\uff12\uff14", B, f"{ERA}/s124", forms=("UK-C-13", "UK-R-01")),
    h("The Sugar Beet (Research and Education) Order 1981", B, SUGAR_BEET, forms=("UK-C-18",), notes="PDF-only instrument: citing it binds"),
    h("Offences against Person Act 1861", B, OAPA, forms=("UK-I-25",), notes="dropped particle"),
    h("Health & Safety at Work etc Act 1974", B, HSWA, forms=("UK-I-25",)),
    h("s. 124(3)(4) of the Employment Rights Act 1996", B, f"{ERA}/s124/3", f"{ERA}/s124/4", forms=("UK-P-18",)),
    h("uk/ukpga/1996/18/s124 is the cap; see also s. 124 ERA 1996", B, f"{ERA}/s124", forms=("UK-X-01", "UK-R-04")),
]

# ---------------------------------------------------------------- invented (never bound)

_MARCHWOOD: Final = "Marchwood is the plan's invented place name (02 §8)"

INVENTED: Final = [
    h("Marchwood Order 2022", I, forms=("UK-I-15", "UK-C-01"), notes=_MARCHWOOD, absent_title=True),
    h("Marchwood Commercial Arbitration Order 2022", I, forms=("UK-I-15",), notes=_MARCHWOOD, absent_title=True),
    h("article 4 of the Marchwood Harbour Revision Order 2019", I, forms=("UK-I-15",), notes=_MARCHWOOD, absent_title=True),
    h("the Marchwood Tramways Act 1998, section 3", I, forms=("UK-I-15",), notes=_MARCHWOOD, absent_title=True),
    h("Moon Mining (Licensing) Act 2016", I, absent_title=True),
    h("section 2 of the Lunar Resources Act 2021", I, absent_title=True),
    h("Artificial Intelligence (Liability) Act 2024", I, absent_title=True),
    h("Garden Gnomes (Registration) Regulations 2013", I, absent_title=True),
    h("regulation 7 of the Hedgehog Crossings (England) Regulations 2018", I, absent_title=True),
    h("Pet Insurance (Mandatory Cover) Act 2012", I, absent_title=True),
    h("Coastal Drones (Registration) Act 2019", I, absent_title=True),
    h("the Remote Working (Right to Disconnect) Act 2022", I, absent_title=True),
    h("Cryptoasset Custody Act 2020, s. 5", I, absent_title=True),
    h("Tidal Energy (Seabed Leasing) Act 2011", I, absent_title=True),
    h("Village Greens (Preservation) Act 2004", I, absent_title=True),
    h("Online Reviews (Honesty) Act 2021", I, absent_title=True),
    h("Rainwater Harvesting (Buildings) Regulations 2016", I, absent_title=True),
    h("Electric Scooters (Speed Limits) Order 2020", I, absent_title=True),
    h("Chess Clubs (Licensing) Regulations 1999", I, absent_title=True),
    h("Bee Keeping (Wales) Act 2015", I, absent_title=True),
    h("Football Stadia (Standing Areas) Act 2023", I, absent_title=True),
    h("section 12 of the Wind Turbines (Noise) Act 2010", I, absent_title=True),
    h("Canal Houseboats (Mooring Fees) Regulations 2008", I, absent_title=True),
    h("Tattoo Parlours (Hygiene) Regulations 2017", I, absent_title=True),
    h("Public Libraries (Late Opening) Act 2005", I, absent_title=True),
    h("Space Tourism (Passenger Safety) Regulations 2025", I, absent_title=True),
    h("Vertical Farming (Planning) Order 2014", I, absent_title=True),
    h("Esports (Integrity) Act 2022", I, absent_title=True),
    h("Beach Huts (Council Tax) Regulations 2012", I, absent_title=True),
    h("Community Orchards Act 2009", I, absent_title=True),
    h("Smart Meters (Data Retention) Regulations 2019", I, absent_title=True),
    h("Wild Swimming (Water Quality) Act 2023", I, absent_title=True),
    h("Rooftop Gardens (Fire Safety) Regulations 2021", I, absent_title=True),
    h("Ice Cream Vans (Chimes) Act 1999", I, absent_title=True),
    h("Allotment Sheds (Permitted Development) Order 2007", I, absent_title=True),
    h("Mobile Phone Masts (Rural Areas) Act 2006", I, absent_title=True),
    h("Escape Rooms (Safety) Regulations 2020", I, absent_title=True),
    h("Street Performers (Licensing) Act 2016", I, absent_title=True),
    h("Pub Quizzes (Gambling) Order 2011", I, absent_title=True),
    h("paragraph 3 of Schedule 2 to the Dog Walkers (Registration) Act 2018", I, absent_title=True),
    h("Charity Shops (Rates Relief) Act 2013", I, absent_title=True),
    h("Solar Canopies (Car Parks) Regulations 2024", I, absent_title=True),
    h("Heritage Railways (Volunteers) Act 2007", I, absent_title=True),
    h("Food Trucks (Trading Pitches) Regulations 2015", I, absent_title=True),
    h("Cycle Couriers (Employment Status) Act 2021", I, absent_title=True),
    h("Pop-up Shops (Business Rates) Order 2018", I, absent_title=True),
    h("Book Festivals (Funding) Act 2003", I, absent_title=True),
    h("Tree Houses (Building Regulations) Order 2010", I, absent_title=True),
    h("Kite Flying (Airspace) Regulations 2002", I, absent_title=True),
    h("Model Railways (Noise) Act 1997", I, absent_title=True),
    h("Employment Rights Act 1995", I, forms=("UK-I-15",), notes="real title, wrong year: ERA 1996 suggested", absent_title=True),
    h(
        "SI 2011/9999",
        I,
        forms=("UK-I-09",),
        notes=(
            "absent: uk/uksi/2011/9999; the source answered HTTP 400 to verify_absence on "
            "29 Sept; recorded from that run's log, since the fetch layer caches only 200, "
            "404 and 410"
        ),
    ),
    h("section 999 of the Employment Rights Act 1996", P, notes="absent: uk/ukpga/1996/18/s999"),
    h("Employment Rights Act 1996 s. 999", P, notes="absent: uk/ukpga/1996/18/s999"),
    h("section 124(9) of the Employment Rights Act 1996", P, notes="absent: uk/ukpga/1996/18/s124/9"),
    h("section 500 of the Theft Act 1968", P, notes="absent: uk/ukpga/1968/60/s500"),
    h("section 77 of the Theft Act 1968", P, notes="absent: uk/ukpga/1968/60/s77"),
    h("regulation 99 of the Working Time Regulations 1998", P, notes="absent: uk/uksi/1998/1833/reg99"),
    h("article 40 of the Employment Rights (Increase of Limits) Order 2011", P, notes="absent: uk/uksi/2011/3006/art40"),
    h("section 1400 of the Companies Act 2006", P, forms=("UK-P-17",), notes="absent: uk/ukpga/2006/46/s1400"),
    h("section 1996 of the Employment Rights Act 1996", P, forms=("UK-P-17",), notes="absent: uk/ukpga/1996/18/s1996; a four-digit provision number is never a year"),
    h("Schedule 9 to the Theft Act 1968", P, notes="absent: uk/ukpga/1968/60/sch9"),
    h("section 30 of the Human Rights Act 1998", P, notes="absent: uk/ukpga/1998/42/s30"),
    h("section 124Z of the Employment Rights Act 1996", P, notes="absent: uk/ukpga/1996/18/s124Z"),
    h("section 250 of the Data Protection Act 2018", P, notes="absent: uk/ukpga/2018/12/s250"),
    h("section 40 of the Fraud Act 2006", P, notes="absent: uk/ukpga/2006/35/s40"),
    h("section 40 of the Bribery Act 2010", P, notes="absent: uk/ukpga/2010/23/s40"),
    h("regulation 80 of the Transfer of Undertakings (Protection of Employment) Regulations 2006", P, notes="absent: uk/uksi/2006/246/reg80"),
]

# ---------------------------------------------------------------- ambiguous

AMBIGUOUS: Final = [
    h("section 124", A, forms=("UK-C-11",)),
    h("s.124", A, forms=("UK-C-11", "UK-P-01")),
    h("the 1996 Act", A, forms=("UK-I-11",), notes="year_only across the Acts of 1996"),
    h("section 124 of the 1996 Act", A, forms=("UK-I-11",), notes="year_only, narrowed to 1996 Acts holding s.124"),
    h("the Act", A, forms=("UK-I-12",), notes="context_needed"),
    h("the Regulations, reg. 4", A, forms=("UK-I-12",)),
    h("c.18", A, forms=("UK-I-08",), notes="a bare chapter without a year"),
    h("Finance Act", A, forms=("UK-I-07",)),
    h("Employment Rights Act", A, ERA, ERA25, forms=("UK-I-07",), notes="Employment Rights Acts 1996 and 2025"),
    h("Working Time Regulations", A, WTR, WTR99, forms=("UK-I-07",), notes="1998 and 1999"),
    h("The Air Navigation Order 1976", A, AIR_NAV_A, AIR_NAV_B, forms=("UK-I-14",), notes="two SIs share the title and year"),
    h("s.98 et seq. of the Employment Rights Act 1996", A, forms=("UK-P-07",)),
    h("section 98 onwards of the Employment Rights Act 1996", A, forms=("UK-P-07",)),
    h("sections 1 to 30 of the Theft Act 1968", A, forms=("UK-P-05", "UK-W-05"), notes="range wider than 20"),
    h("Parts II to IV of the Employment Rights Act 1996", A, forms=("UK-P-13",), notes="range"),
    h("Employment Rights Act 1996 (c. 17)", A, ERA, ETA, forms=("UK-I-21",), notes="chapter_mismatch: c. 17 of 1996 is the Employment Tribunals Act"),
    h("Marchwood Order 2011 (S.I. 2011/3006)", A, forms=("UK-I-30",), notes="title_number_conflict"),
    h("Marchwood Act 1996 (c. 18)", A, forms=("UK-I-21",), notes="title_number_conflict"),
    h("The Employment Rights (Increase of Limits) Order 2011 (S.I. 2026/310)", A, SI_2011, SI_2026, forms=("UK-I-30",), notes="number_mismatch"),
    h("FA 2023", A, forms=("UK-I-28",), notes="Finance Act 2023 or Firearms Act 2023"),
    h("IA 1986 Sch. B1 para. 15(3)", A, forms=("UK-C-21",), notes="duplicated_in_source (decision 13)"),
    h("In the Employment Rights Act 1996 and the Equality Act 2010, what does section 124 cover?", A, forms=("UK-C-20",)),
    h("section 124 except section 125", A, forms=("UK-C-07", "UK-L-04"), notes="an exclusion with no instrument to scope it"),
    h("The Theft Act 1968 applies. Section 1 defines theft.", A, forms=("UK-L-02",), notes="the sentence end breaks the link"),
    h("marchwood commercial arbitration act 1996", A, ARB, forms=("UK-I-20",), notes="lower case: 'Did you mean the Arbitration Act 1996?'"),
]

# ---------------------------------------------------------------- typo (D2: split dev/test)
# Real titles misspelled the way people do it: BOUNDED when one small typo in one word of
# five letters or more; AMBIGUOUS with the right top candidate for bigger typos.
# Adversarial near-misses: never BOUNDED.

TYPO: Final = [
    h("Employment Rihgts Act 1996 s.124", B, f"{ERA}/s124", forms=("UK-I-16",), notes="rihgts→rights"),
    h("Employment Rihgts Act 1996", B, ERA, forms=("UK-I-16",), notes="rihgts→rights"),
    h("Employmnet Rights Act 1996", B, ERA, forms=("UK-I-16",), notes="transposition"),
    h("Emplyment Rights Act 1996", B, ERA, forms=("UK-I-16",), notes="dropped letter"),
    h("employment rihgts act 1996", B, ERA, forms=("UK-I-16", "UK-I-02"), notes="lower case"),
    h("EMPLOYMENT RIHGTS ACT 1996", B, ERA, forms=("UK-I-16", "UK-C-15"), notes="ALL CAPS"),
    h("Equailty Act 2010", B, EQA, forms=("UK-I-16",)),
    h("Equalty Act 2010 s. 13", B, f"{EQA}/s13", forms=("UK-I-16",)),
    h("Thetf Act 1968", B, THEFT, forms=("UK-I-16",)),
    h("Arbitraiton Act 1996", B, ARB, forms=("UK-I-16",)),
    h("Companeis Act 2006", B, CA06, forms=("UK-I-16",)),
    h("Insolvancy Act 1986", B, IA86, forms=("UK-I-16",)),
    h("Human Rigths Act 1998", B, HRA, forms=("UK-I-16",)),
    h("Data Protecion Act 2018", B, DPA18, forms=("UK-I-16",)),
    h("Criminal Justcie Act 2003", B, CJA03, forms=("UK-I-16",)),
    h("Chidlren Act 1989", B, CHILDREN, forms=("UK-I-16",)),
    h("Misuse of Drgus Act 1971", B, MDA, forms=("UK-I-16",)),
    h("Mental Capcity Act 2005", B, MCA05, forms=("UK-I-16",)),
    h("Freedom of Informaton Act 2000", B, FOIA, forms=("UK-I-16",)),
    h("Limitaton Act 1980", B, LIMITATION, forms=("UK-I-16",)),
    h("Consumer Rigths Act 2015", B, CRA15, forms=("UK-I-16",)),
    h("Environmental Protecton Act 1990", B, EPA90, forms=("UK-I-16",)),
    h("Town and Country Planing Act 1990", B, TCPA90, forms=("UK-I-16",)),
    h("Road Trafic Act 1988", B, RTA88, forms=("UK-I-16",)),
    h("Sale of Godos Act 1979", B, SGA79, forms=("UK-I-16",)),
    h("Partnreship Act 1890", B, PARTNERSHIP, forms=("UK-I-16",)),
    h("Bills of Exhcange Act 1882", B, BILLS, forms=("UK-I-16",)),
    h("Ofences against the Person Act 1861", B, OAPA, forms=("UK-I-16",)),
    h("Health and Saftey at Work etc. Act 1974", B, HSWA, forms=("UK-I-16",)),
    h("Workign Time Regulations 1998", B, WTR, forms=("UK-I-16",)),
    h("Transfer of Undertakngs (Protection of Employment) Regulations 2006", B, TUPE, forms=("UK-I-16",)),
    h("National Minimun Wage Regulations 2015", B, NMW, forms=("UK-I-16",)),
    h("Civil Procedrue Rules 1998", B, CPR, forms=("UK-I-16",)),
    h("Managment of Health and Safety at Work Regulations 1999", B, MHSW, forms=("UK-I-16",)),
    h("Fruad Act 2006", B, FRAUD, forms=("UK-I-16",)),
    h("Bribrey Act 2010", B, BRIBERY, forms=("UK-I-16",)),
    h("Police and Criminal Evidnce Act 1984", B, PACE, forms=("UK-I-16",)),
    h("Protection from Harrassment Act 1997", B, PHA97, forms=("UK-I-16",)),
    h("Computer Missuse Act 1990", B, CMA90, forms=("UK-I-16",)),
    h("Employment Right Act 1996", B, ERA, forms=("UK-I-16",), notes="singular for plural"),
    h("Rights of Employment Act 1996", B, ERA, forms=("UK-I-18",), notes="reordered"),
    h("Protection of Data Act 2018", B, DPA18, forms=("UK-I-18",), notes="reordered"),
    h("Rights of Consumer Act 2015", B, CRA15, forms=("UK-I-18",), notes="reordered"),
    h("Information Freedom Act 2000", B, FOIA, forms=("UK-I-18",), notes="reordered"),
    h("Emplyment Rihgts Act 1996", A, ERA, forms=("UK-I-17",), notes="two misspelled words"),
    h("Humna Rigths Act 1998", A, HRA, forms=("UK-I-17",), notes="two misspelled words"),
    h("Arbtiraiton Act 1996", A, ARB, forms=("UK-I-17",), notes="two edits in one word"),
    h("Insolvncey Act 1986", A, IA86, forms=("UK-I-17",), notes="two edits in one word"),
    h("Contracts (Rights of Third Partys) Act 1999", A, "uk/ukpga/1999/31", forms=("UK-I-17",), notes="two edits in one word"),
    h("Rights of Employmnet Act 1996", A, ERA, forms=("UK-I-17", "UK-I-18"), notes="reordered and a typo"),
    # adversarial: never BOUNDED
    h("Family Rights Act 1996", I, forms=("UK-I-15",), notes="semantic neighbour of ERA 1996", absent_title=True),
    h("Employment Rights Act 1995", I, forms=("UK-I-15",), notes="wrong year", absent_title=True),
    h("rights of employment act 1990", I, forms=("UK-I-15",), notes="wrong year and reordered: ERA 1996 suggested", absent_title=True),
    h("Marchwood Commercial Arbitration Act 1996", I, forms=("UK-I-19",), notes="invented words before a real title", absent_title=True),
    h("marchwood commercial arbitration act 1996", A, ARB, forms=("UK-I-20",), notes="lower case"),
    h("Marchwood Theft Act 1968", I, forms=("UK-I-19",), absent_title=True),
    h("marchwood theft act 1968", A, THEFT, forms=("UK-I-20",), notes="lower case"),
    h("Consumer Wrongs Act 2015", I, notes="semantic neighbour of the Consumer Rights Act 2015", absent_title=True),
    h("Animal Rights Act 2006", I, notes="semantic neighbour of the Animal Welfare Act 2006", absent_title=True),
    h("Theft Act 1986", I, notes="transposed year", absent_title=True),
    h("Data Protection Act 2017", I, notes="wrong year", absent_title=True),
    h("Human Rights Act 1989", I, notes="transposed year", absent_title=True),
    h("Equality Act 2011", I, notes="wrong year", absent_title=True),
    h("Companies Act 2007", I, notes="wrong year", absent_title=True),
    h("Fraud Act 2016", I, notes="wrong year", absent_title=True),
    h("Bribery Act 2001", I, notes="wrong year", absent_title=True),
    h("Employment Wrongs Act 1996", I, notes="semantic neighbour", absent_title=True),
    h("Unemployment Rights Act 1996", I, notes="one word added in front", absent_title=True),
    h("Employment Rights (Marchwood) Act 1996", I, notes="invented word inside a real title", absent_title=True),
    h("Data Collection Act 2018", I, notes="semantic neighbour of the Data Protection Act 2018", absent_title=True),
    h("Mental Health Capacity Act 2005", I, notes="two real titles blended", absent_title=True),
    h("Children and Families Protection Act 1989", I, notes="semantic neighbour", absent_title=True),
    h("Proceeds of Fraud Act 2002", I, notes="semantic neighbour of the Proceeds of Crime Act 2002", absent_title=True),
    h("Working Hours Regulations 1998", I, notes="semantic neighbour of the Working Time Regulations 1998", absent_title=True),
    h("Working Time Regulations 1997", I, notes="wrong year", absent_title=True),
]

# ---------------------------------------------------------------- identifier

IDENTIFIER: Final = [
    h("uk/ukpga/1996/18/s124", B, f"{ERA}/s124", forms=("UK-X-01",)),
    h("uk/ukpga/1996/18/s124/1ZA/a", B, f"{ERA}/s124/1ZA/a", forms=("UK-X-01",)),
    h("UK/UKPGA/1996/18/S124", B, f"{ERA}/s124", forms=("UK-X-01",), notes="any case: canonical case from the index"),
    h("uk/ukpga/1996/18", B, ERA, forms=("UK-X-01",)),
    h("uk/uksi/2011/3006/art3", B, f"{SI_2011}/art3", forms=("UK-X-01",)),
    h("uk/ukpga/Vict/24-25/100/s18", B, f"{OAPA}/s18", forms=("UK-X-01",)),
    h("uk_ukpga_1996_18", B, ERA, forms=("UK-X-02",)),
    h("uk_uksi_2011_3006", B, SI_2011, forms=("UK-X-02",)),
    h("uk_ukpga_Vict_24-25_100", B, OAPA, forms=("UK-X-02",)),
    h("https://www.legislation.gov.uk/ukpga/1996/18/section/124", B, f"{ERA}/s124", forms=("UK-X-03",)),
    h("https://www.legislation.gov.uk/id/ukpga/1996/18/section/124", B, f"{ERA}/s124", forms=("UK-X-03",)),
    h("http://www.legislation.gov.uk/ukpga/1996/18/contents", B, ERA, forms=("UK-X-03",)),
    h("legislation.gov.uk/ukpga/1996/18/section/124/enacted", B, f"{ERA}/s124", forms=("UK-X-03",)),
    h("https://www.legislation.gov.uk/uksi/2011/3006/article/3/made", B, f"{SI_2011}/art3", forms=("UK-X-03",)),
    h("https://www.legislation.gov.uk/ukpga/1996/18/section/124/2020-01-01", B, f"{ERA}/s124", forms=("UK-X-03",)),
    h("https://www.legislation.gov.uk/ukpga/1996/18/data.xml", B, ERA, forms=("UK-X-03",)),
    h("https://www.legislation.gov.uk/ukpga/Vict/24-25/100/section/18", B, f"{OAPA}/s18", forms=("UK-X-03",)),
    h("see https://www.legislation.gov.uk/ukpga/1996/18/section/124 for the cap", B, f"{ERA}/s124", forms=("UK-X-03",)),
    h("uk/ukpga/1996/18 section 124", B, f"{ERA}/s124", forms=("UK-X-04",)),
    h("uk_ukpga_1996_18 s.98", B, f"{ERA}/s98", forms=("UK-X-04",)),
    h("uk/ukpga/1996/999", I, forms=("UK-X-01",), notes="absent: uk/ukpga/1996/999"),
    h("uk_ukpga_1996_999", I, forms=("UK-X-02",), notes="absent: uk/ukpga/1996/999"),
    h("https://www.legislation.gov.uk/ukpga/1996/999", I, forms=("UK-X-03",), notes="absent: uk/ukpga/1996/999"),
    h("uk/ukpga/1996/18/s124/9", P, forms=("UK-X-01",), notes="absent: uk/ukpga/1996/18/s124/9"),
    h("https://www.legislation.gov.uk/ukpga/1996/18/section/999", P, forms=("UK-X-03",), notes="absent: uk/ukpga/1996/18/s999"),
    h("uk/ukpga/1996", U, forms=("UK-X-05",), notes="a partial path is not a citation"),
    h("uk/ukpga/1996/18' or '1'=='1", B, ERA, forms=("UK-X-01",), notes="injection-shaped: only the safe key uk/ukpga/1996/18 is read; the quoted tail never reaches the filter"),
    h("uk_ukpga_1996_18; DROP TABLE provisions;--", B, ERA, forms=("UK-X-02",), notes="injection-shaped: only the safe key is read"),
    h("uk/ukpga/1996/18/s124\" OR coordinate LIKE \"%", B, f"{ERA}/s124", forms=("UK-X-01",), notes="injection-shaped: only the safe key is read"),
]

# ---------------------------------------------------------------- informal
# Missing type word or year, mixed-up provision words: BOUNDED when exactly one instrument
# fits, otherwise AMBIGUOUS; never an abstention.

INFORMAL: Final = [
    h("employment rights 1996 s124", B, f"{ERA}/s124", forms=("UK-I-06",)),
    h("employment rights act section 124", A, ERA, ERA25, forms=("UK-I-07",), notes="Employment Rights Acts 1996 and 2025 both have s. 124"),
    h("Employment Rights Act 1996 article 124", B, f"{ERA}/s124", forms=("UK-P-15",)),
    h("ERA s.124", A, forms=("UK-C-11",), notes="'ERA' has no curated year-less form: a bare provision"),
    h("equality act 2010 s 13", B, f"{EQA}/s13", forms=("UK-I-02",)),
    h("data protection 2018 section 170", B, f"{DPA18}/s170", forms=("UK-I-06",)),
    h("human rights act s3", B, f"{HRA}/s3", forms=("UK-I-07",)),
    h("HRA s.3", B, f"{HRA}/s3", forms=("UK-I-05",)),
    h("tulrca s.188", B, f"{TULRCA}/s188", forms=("UK-I-05",)),
    h("FSMA s 19", B, f"{FSMA}/s19", forms=("UK-I-05",)),
    h("hswa s2", B, f"{HSWA}/s2", forms=("UK-I-05",)),
    h("OAPA s 18", B, f"{OAPA}/s18", forms=("UK-I-05",)),
    h("Employment Rights Act, section 98", A, ERA, ERA25, forms=("UK-I-07",), notes="both Acts have s. 98"),
    h("unfair dismissal section 98 employment rights act", A, ERA, ERA25, forms=("UK-I-07",)),
    h("section 124 employment rights act 1996", B, f"{ERA}/s124", forms=("UK-L-01",)),
    h("section 13 of the equality act", A, EQA06, EQA, forms=("UK-I-07",), notes="Equality Acts 2006 and 2010"),
    h("companies act 2006 s.1", B, f"{CA06}/s1", forms=("UK-I-02",)),
    h("the Theft Act, s. 1", A, forms=("UK-I-07",)),
    h("Finance Act s 1", A, forms=("UK-I-07",)),
    h("companies act s 124", A, forms=("UK-I-07",)),
    h("working time regulations reg 4", A, WTR, WTR99, forms=("UK-I-07",)),
    h("insolvency act 1986 schedule B1 paragraph 14", B, f"{IA86}/schB1/para14", forms=("UK-P-08a",)),
    h("the Employment Rights (Increase of Limits) Order 2011 section 3", B, f"{SI_2011}/art3", forms=("UK-P-15",), notes="section of an SI read as its article"),
    h("in the ERA 1996, what's in s.124?", B, f"{ERA}/s124", forms=("UK-C-20",)),
    h("what does the Equality Act 2010 say in section 13", B, f"{EQA}/s13", forms=("UK-L-02",)),
    h("the arbitration act 1996 s 68 challenge", B, f"{ARB}/s68", forms=("UK-I-02",)),
    h("s 1 fraud act", B, f"{FRAUD}/s1", forms=("UK-I-07",)),
]

# ---------------------------------------------------------------- catalogue
# At least one row per case-catalogue entry (grammar.md 4.4 to 6).

_GDPR: Final = "Article 82 UK GDPR"

CATALOGUE: Final = [
    h("Marchwood Order 2022", I, forms=("UK-C-01",), notes="index_snapshot is set", absent_title=True),
    h("Employment Rights (Increase of Limits) Order 2011 article 3", B, f"{SI_2011}/art3", forms=("UK-C-02",), notes="repealed=True"),
    h("what about section 125?", B, f"{ERA}/s125", forms=("UK-C-03",), context=(f"{ERA}/s124",)),
    h("what about section 13 of the Equality Act 2010?", B, f"{EQA}/s13", forms=("UK-C-04",), context=(f"{ERA}/s124",)),
    h("and s. 98?", B, f"{ERA}/s98", forms=("UK-C-03",), context=(ERA,)),
    h("what about section 125?", A, forms=("UK-C-05",), context=("uk/ukpga/1996/999/s1",)),
    h("s.124, not the Companies Act one, the ERA 1996", B, f"{ERA}/s124", forms=("UK-C-06",)),
    h("section 124 except section 125", A, forms=("UK-C-07",)),
    h("In the ERA 1996, what applies across all sections except section 124?", B, ERA, forms=("UK-C-19", "UK-L-04"), notes="excluded=[…/s124]"),
    h("In the Employment Rights Act 1996, what does section 124 cover?", B, f"{ERA}/s124", forms=("UK-C-20",)),
    h("IA 1986 Sch. B1 para. 15(3)", A, forms=("UK-C-21",)),
    h(f"ERA 1996 s.124 and {_GDPR}", O, forms=("UK-C-22", "UK-O-02")),
    h("section 124 of the Employment Rights Act 1996 as it stood in 2012", B, f"{ERA}/s124", forms=("UK-C-08",)),
    h("sections 94 and 98 of the ERA 1996 and section 13 of the Equality Act 2010", B, f"{ERA}/s94", f"{ERA}/s98", f"{EQA}/s13", forms=("UK-C-09",)),
    h("ERA 1996 s.124 and section 500 of the Theft Act 1968", P, forms=("UK-C-10",), notes="absent: uk/ukpga/1968/60/s500"),
    h("section 124", A, forms=("UK-C-11",)),
    h("£124 for 124 employees from 1 April 1996", U, forms=("UK-C-12", "UK-L-05")),
    h("section\u00a0124 of the Employment Rights Act\u00a01996", B, f"{ERA}/s124", forms=("UK-C-13",)),
    h("Employment Rights \u0410ct 1996 s.124", B, f"{ERA}/s124", forms=("UK-C-14",)),
    h("SECTION 124 OF THE EMPLOYMENT RIGHTS ACT 1996", B, f"{ERA}/s124", forms=("UK-C-15",)),
    h("section 124 " * 400, U, forms=("UK-C-16", "UK-W-01"), notes="4,800 characters: query_too_long"),
    h("art. 3 of the Sugar Beet (Research and Education) Order 1981", O, forms=("UK-C-18",), notes="provision structure not available; VERIFY_LIVE"),
    h("Criminal Justice and Licensing (Scotland) Act 2010", O, forms=("UK-O-01",)),
    h("Royal Exchange Assurance Act 1901", O, forms=("UK-O-01",), notes="local Act (ukla)"),
    h("SSI 2003/623", O, forms=("UK-O-01",), notes="Scottish SI series is not indexed"),
    h("SR 1996/123", O, forms=("UK-O-01",), notes="Northern Ireland Statutory Rules are not indexed"),
    h(_GDPR, O, forms=("UK-O-02",)),
    h("Regulation (EU) 2016/679", O, forms=("UK-O-02",)),
    h("Employment Rights Bill", O, forms=("UK-O-03",)),
    h("[2020] UKSC 1", O, forms=("UK-O-04",)),
    h("[2019] EWCA Civ 123", O, forms=("UK-O-04",)),
    h("article 1240 of the Code civil", O, forms=("UK-O-05",)),
    h("BGB § 823", O, forms=("UK-O-05",)),
    h("42 U.S.C. § 1983", O, forms=("UK-O-05",)),
    h("art. 42 CdC", O, forms=("UK-O-06",)),
    h("Ley 58/2003", O, forms=("UK-O-06",)),
    h("S. 999 inserted by Employment Rights Act 1996", B, ERA, forms=("UK-L-03",), notes="the provision belongs to the amended Act and is left unlinked"),
    h("what is the law on unfair dismissal", U, forms=("UK-W-02", "UK-U-01")),
    h("Theft Act 1968 and " * 25 + "the Fraud Act 2006", U, forms=("UK-W-03",), notes="more than 24 instrument mentions: too_complex"),
    h("The " + " ".join(["Marchwood"] * 22) + " Act 2010", U, forms=("UK-W-04",), notes="an unknown title longer than 20 words is left unread, never refused"),
    h("the unfair dismissal law", U, forms=("UK-U-01",)),
    h("subsection (2) above", U, forms=("UK-U-02",)),
    h("the explanatory notes to the Equality Act 2010", U, forms=("UK-U-03",), notes="pinpoints to explanatory notes are unsupported"),
    h("the Bribery law", U, forms=("UK-U-04",)),
    h("2005/275", U, forms=("UK-U-05",)),
]
