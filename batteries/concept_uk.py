# ruff: noqa: E501 - one row per line reads best as a table
"""Drafted concept queries for the stage-D battery (docs/discovery.md, roadmap D2).

Keyword strings in the style of Mart (2017) Appendix B: factual context + doctrinal element
+ procedural or remedial posture, no citation. Each row names the provisions that answer it
(``gold``: any one of them, or anything beneath one, is a hit). Written from the doctrine
first; ``build_concepts.py`` then checks every gold coordinate exists and prints its heading
for review. A query is never reworded to match a heading. The 15 D0 probe queries are not
reused here.
"""

from __future__ import annotations

from typing import Final

# fmt: off
ERA: Final = "uk/ukpga/1996/18"
EQA: Final = "uk/ukpga/2010/15"
TULRCA: Final = "uk/ukpga/1992/52"
NMWA: Final = "uk/ukpga/1998/39"
WTR: Final = "uk/uksi/1998/1833"
TUPE: Final = "uk/uksi/2006/246"
THEFT: Final = "uk/ukpga/1968/60"
FRAUD: Final = "uk/ukpga/2006/35"
BRIBERY: Final = "uk/ukpga/2010/23"
OAPA: Final = "uk/ukpga/Vict/24-25/100"
CDA71: Final = "uk/ukpga/1971/48"
MDA: Final = "uk/ukpga/1971/38"
CMA90: Final = "uk/ukpga/1990/18"
PHA: Final = "uk/ukpga/1997/40"
POA86: Final = "uk/ukpga/1986/64"
RTA88: Final = "uk/ukpga/1988/52"
POCA: Final = "uk/ukpga/2002/29"
PACE: Final = "uk/ukpga/1984/60"
CJPOA: Final = "uk/ukpga/1994/33"
BAIL: Final = "uk/ukpga/1976/63"
CJA03: Final = "uk/ukpga/2003/44"
CPIA: Final = "uk/ukpga/1996/25"
SA20: Final = "uk/ukpga/2020/17"
MCA80: Final = "uk/ukpga/1980/43"
ROA74: Final = "uk/ukpga/1974/53"
LTA85: Final = "uk/ukpga/1985/70"
LTA87: Final = "uk/ukpga/1987/31"
HA88: Final = "uk/ukpga/1988/50"
HA96: Final = "uk/ukpga/1996/52"
HA04: Final = "uk/ukpga/2004/34"
HA85: Final = "uk/ukpga/1985/68"
PEA77: Final = "uk/ukpga/1977/43"
LTA54: Final = "uk/ukpga/Eliz2/2-3/56"
LRHUDA: Final = "uk/ukpga/1993/28"
LPA25: Final = "uk/ukpga/Geo5/15-16/20"
LPMPA89: Final = "uk/ukpga/1989/34"
LRA02: Final = "uk/ukpga/2002/9"
TLATA: Final = "uk/ukpga/1996/47"
PWA96: Final = "uk/ukpga/1996/40"
CA06: Final = "uk/ukpga/2006/46"
CDDA: Final = "uk/ukpga/1986/46"
IA86: Final = "uk/ukpga/1986/45"
CRA15: Final = "uk/ukpga/2015/15"
UCTA: Final = "uk/ukpga/1977/50"
CRTPA: Final = "uk/ukpga/1999/31"
SGA: Final = "uk/ukpga/1979/54"
MISREP: Final = "uk/ukpga/1967/7"
LRFCA: Final = "uk/ukpga/Geo6/6-7/40"
LPCDIA: Final = "uk/ukpga/1998/20"
CPA87: Final = "uk/ukpga/1987/43"
LIMITATION: Final = "uk/ukpga/1980/58"
FOIA: Final = "uk/ukpga/2000/36"
DPA18: Final = "uk/ukpga/2018/12"
IPA16: Final = "uk/ukpga/2016/25"
PECR: Final = "uk/uksi/2003/2426"
EIR: Final = "uk/uksi/2004/3391"
CHA89: Final = "uk/ukpga/1989/41"
MCA73: Final = "uk/ukpga/1973/18"
IPFDA: Final = "uk/ukpga/1975/63"
WILLS: Final = "uk/ukpga/Will4and1Vict/7/26"
FLA96: Final = "uk/ukpga/1996/27"
ACA02: Final = "uk/ukpga/2002/38"
DAA21: Final = "uk/ukpga/2021/17"
MCA05: Final = "uk/ukpga/2005/9"
ITA07: Final = "uk/ukpga/2007/3"
TCGA: Final = "uk/ukpga/1992/12"
ITEPA: Final = "uk/ukpga/2003/1"
IHTA: Final = "uk/ukpga/1984/51"
VATA: Final = "uk/ukpga/1994/23"
FA03: Final = "uk/ukpga/2003/14"
CTA09: Final = "uk/ukpga/2009/4"
FA13: Final = "uk/ukpga/2013/29"
FA07: Final = "uk/ukpga/2007/11"
TMA: Final = "uk/ukpga/1970/9"
ITTOIA: Final = "uk/ukpga/2005/5"

AREAS: Final = (
    "employment", "equality", "criminal_offences", "criminal_procedure", "housing",
    "land", "companies", "insolvency", "consumer_contract", "data_information",
    "family", "tax",
)

DRAFTED: Final[list[tuple[str, str, tuple[str, ...]]]] = [
    # (area, query, gold)
    # -- employment
    ("employment", "employee written statement employment particulars start date pay hours", (f"{ERA}/s1",)),
    ("employment", "employer deducts wages without consent unlawful deduction", (f"{ERA}/s13",)),
    ("employment", "wages deduction complaint employment tribunal time limit three months", (f"{ERA}/s23",)),
    ("employment", "employee right not unfairly dismissed", (f"{ERA}/s94",)),
    ("employment", "two years continuous employment qualifying period unfair dismissal claim", (f"{ERA}/s108",)),
    ("employment", "fair reason dismissal conduct capability redundancy reasonableness", (f"{ERA}/s98",)),
    ("employment", "employee resigns employer repudiatory breach constructive dismissal", (f"{ERA}/s95",)),
    ("employment", "sacked for being pregnant automatically unfair dismissal", (f"{ERA}/s99",)),
    ("employment", "whistleblower dismissed principal reason protected disclosure automatically unfair", (f"{ERA}/s103A",)),
    ("employment", "unfair dismissal basic award calculation age years service week's pay", (f"{ERA}/s119",)),
    ("employment", "tribunal order reinstatement re-engagement dismissed employee remedy", (f"{ERA}/s113", f"{ERA}/s114", f"{ERA}/s115")),
    ("employment", "redundancy payment entitlement employee dismissed by reason of redundancy", (f"{ERA}/s135",)),
    ("employment", "meaning redundancy workplace closure diminished need for employees", (f"{ERA}/s139",)),
    ("employment", "unreasonable refusal suitable alternative employment lose redundancy pay", (f"{ERA}/s141",)),
    ("employment", "time off work magistrate jury public duties employee", (f"{ERA}/s50",)),
    ("employment", "worker entitlement national minimum wage", (f"{NMWA}/s1",)),
    ("employment", "maximum weekly working time 48 hours average opt out", (f"{WTR}/reg4",)),
    ("employment", "paid annual leave entitlement weeks worker holiday", (f"{WTR}/reg13", f"{WTR}/reg13A")),
    ("employment", "industrial action ballot union before strike", (f"{TULRCA}/s226",)),
    ("employment", "collective redundancies consult representatives 20 or more employees", (f"{TULRCA}/s188",)),
    ("employment", "business sale employees contracts transfer automatically new employer", (f"{TUPE}/reg4",)),
    # -- equality
    ("equality", "list protected characteristics discrimination law", (f"{EQA}/s4",)),
    ("equality", "less favourable treatment because of protected characteristic direct discrimination", (f"{EQA}/s13",)),
    ("equality", "neutral policy puts group at particular disadvantage indirect discrimination justification", (f"{EQA}/s19",)),
    ("equality", "employer failed adjust workplace substantial disadvantage disabled worker claim", (f"{EQA}/s20", f"{EQA}/s21")),
    ("equality", "unwanted conduct violating dignity hostile environment harassment", (f"{EQA}/s26",)),
    ("equality", "detriment for bringing discrimination complaint victimisation", (f"{EQA}/s27",)),
    ("equality", "meaning disability long-term substantial adverse effect day-to-day activities", (f"{EQA}/s6", f"{EQA}/sch1")),
    ("equality", "unfavourable treatment something arising in consequence of disability", (f"{EQA}/s15",)),
    ("equality", "woman paid less than man like work equal pay sex equality clause", (f"{EQA}/s66", f"{EQA}/s65", f"{EQA}/s64")),
    ("equality", "dismissed during maternity leave pregnancy discrimination work", (f"{EQA}/s18",)),
    ("equality", "burden of proof discrimination claim shifts respondent explanation", (f"{EQA}/s136",)),
    ("equality", "discrimination claim employment tribunal time limit just and equitable extension", (f"{EQA}/s123",)),
    ("equality", "positive action recruitment tie-break under-represented group", (f"{EQA}/s159", f"{EQA}/s158")),
    ("equality", "public authority due regard eliminate discrimination equality duty", (f"{EQA}/s149",)),
    ("equality", "gender reassignment protected characteristic transition", (f"{EQA}/s7",)),
    ("equality", "genuine occupational requirement exception discrimination recruitment", (f"{EQA}/sch9/para1",)),
    ("equality", "employer liable for employee's discrimination all reasonable steps defence", (f"{EQA}/s109",)),
    # -- criminal offences
    ("criminal_offences", "theft using force or threat of force robbery", (f"{THEFT}/s8",)),
    ("criminal_offences", "enters building as trespasser intent to steal burglary", (f"{THEFT}/s9",)),
    ("criminal_offences", "dishonestly receiving stolen goods handling offence", (f"{THEFT}/s22",)),
    ("criminal_offences", "lying to obtain gain dishonest false representation offence", (f"{FRAUD}/s2",)),
    ("criminal_offences", "employee abuses trusted position dishonestly fraud", (f"{FRAUD}/s4",)),
    ("criminal_offences", "offering financial advantage induce improper performance bribery", (f"{BRIBERY}/s1",)),
    ("criminal_offences", "company failed prevent bribery associated person adequate procedures defence", (f"{BRIBERY}/s7",)),
    ("criminal_offences", "punch causing bruising assault occasioning actual bodily harm", (f"{OAPA}/s47",)),
    ("criminal_offences", "wounding inflicting grievous bodily harm without intent", (f"{OAPA}/s20",)),
    ("criminal_offences", "destroying damaging property belonging to another without lawful excuse", (f"{CDA71}/s1",)),
    ("criminal_offences", "possession controlled drug intent to supply", (f"{MDA}/s5",)),
    ("criminal_offences", "hacking unauthorised access computer material offence", (f"{CMA90}/s1",)),
    ("criminal_offences", "course of conduct harassment criminal offence", (f"{PHA}/s2", f"{PHA}/s1")),
    ("criminal_offences", "stalking behaviour offence fear alarm", (f"{PHA}/s2A", f"{PHA}/s4A")),
    ("criminal_offences", "threatening abusive words fear of immediate unlawful violence", (f"{POA86}/s4",)),
    ("criminal_offences", "causing death dangerous driving offence", (f"{RTA88}/s1",)),
    ("criminal_offences", "driving over prescribed alcohol limit drink driving", (f"{RTA88}/s5",)),
    ("criminal_offences", "concealing converting criminal property money laundering", (f"{POCA}/s327",)),
    # -- criminal procedure and evidence
    ("criminal_procedure", "police stop search person reasonable grounds suspect stolen articles", (f"{PACE}/s1",)),
    ("criminal_procedure", "constable arrest without warrant necessity criteria", (f"{PACE}/s24",)),
    ("criminal_procedure", "detained person police custody limit 24 hours without charge", (f"{PACE}/s41",)),
    ("criminal_procedure", "arrested suspect right consult solicitor privately police station", (f"{PACE}/s58",)),
    ("criminal_procedure", "court exclude prosecution evidence adverse effect fairness proceedings", (f"{PACE}/s78",)),
    ("criminal_procedure", "confession obtained by oppression inadmissible", (f"{PACE}/s76",)),
    ("criminal_procedure", "magistrate issue warrant enter search premises evidence indictable offence", (f"{PACE}/s8",)),
    ("criminal_procedure", "adverse inference failure mention fact police interview silence", (f"{CJPOA}/s34",)),
    ("criminal_procedure", "defendant general right to bail presumption", (f"{BAIL}/s4",)),
    ("criminal_procedure", "hearsay statement admissible criminal proceedings interests of justice", (f"{CJA03}/s114",)),
    ("criminal_procedure", "defendant previous convictions bad character evidence gateways", (f"{CJA03}/s101",)),
    ("criminal_procedure", "prosecutor initial disclosure unused material undermine case", (f"{CPIA}/s3",)),
    ("criminal_procedure", "credit early guilty plea sentence reduction", (f"{SA20}/s73",)),
    ("criminal_procedure", "summary offence information laid within six months time limit", (f"{MCA80}/s127",)),
    ("criminal_procedure", "spent convictions rehabilitation period job applicant disclosure", (f"{ROA74}/s1", f"{ROA74}/s4", f"{ROA74}/s5")),
    ("criminal_procedure", "age of criminal responsibility children under ten", ("uk/ukpga/Geo5/23-24/12/s50",)),
    ("criminal_procedure", "surveillance authorisation directed covert investigation", ("uk/ukpga/2000/23/s28",)),
    # -- housing and tenancy
    ("housing", "landlord repair structure exterior short residential lease", (f"{LTA85}/s11",)),
    ("housing", "rented home unfit for human habitation landlord obligation", (f"{LTA85}/s9A",)),
    ("housing", "tenancy deposit not protected scheme landlord penalty", (f"{HA04}/s213", f"{HA04}/s214")),
    ("housing", "assured tenancy court order possession grounds", (f"{HA88}/s7", f"{HA88}/sch2")),
    ("housing", "landlord increase rent periodic assured tenancy notice", (f"{HA88}/s13",)),
    ("housing", "tenant challenge service charges reasonable incurred tribunal", (f"{LTA85}/s19", f"{LTA85}/s27A")),
    ("housing", "leaseholder consultation major works service charge limit", (f"{LTA85}/s20",)),
    ("housing", "landlord changed locks tenant unlawful eviction offence", ("uk/ukpga/1977/43/s1",)),
    ("housing", "notice to quit dwelling minimum four weeks", ("uk/ukpga/1977/43/s5",)),
    ("housing", "council homelessness priority need vulnerable applicant", (f"{HA96}/s189",)),
    ("housing", "local authority main housing duty homeless applicant accommodation", (f"{HA96}/s193",)),
    ("housing", "shared house multiple occupation licence required", (f"{HA04}/s61", f"{HA04}/s55")),
    ("housing", "business tenant lease continues security of tenure", (f"{LTA54}/s24",)),
    ("housing", "council tenant right to buy home", (f"{HA85}/s118",)),
    ("housing", "flat owners collective enfranchisement buy freehold", (f"{LRHUDA}/s1",)),
    ("housing", "landlord must give tenant address for service of notices", (f"{LTA87}/s48",)),
    # -- land and property
    ("land", "contract sale land must be in writing signed both parties", (f"{LPMPA89}/s2",)),
    ("land", "only legal estates fee simple term of years absolute", (f"{LPA25}/s1",)),
    ("land", "purchaser pays two trustees overreaching beneficial interests", (f"{LPA25}/s2", f"{LPA25}/s27")),
    ("land", "landlord forfeiture breach covenant notice specifying breach relief", (f"{LPA25}/s146",)),
    ("land", "squatter adverse possession registered land ten years application", (f"{LRA02}/sch6", f"{LRA02}/s97")),
    ("land", "registrable dispositions must be completed by registration", (f"{LRA02}/s27",)),
    ("land", "person in actual occupation overriding interest registered disposition", (f"{LRA02}/sch3",)),
    ("land", "co-owner applies court order sale jointly owned home", (f"{TLATA}/s14", f"{TLATA}/s15")),
    ("land", "conveyance passes easements rights general words", (f"{LPA25}/s62",)),
    ("land", "declaration of trust of land writing signed", (f"{LPA25}/s53",)),
    ("land", "discharge modify restrictive covenant upper tribunal", (f"{LPA25}/s84",)),
    ("land", "building owner notice adjoining owner party wall works", (f"{PWA96}/s1", f"{PWA96}/s3", f"{PWA96}/s2")),
    ("land", "right of way twenty years use prescription", ("uk/ukpga/Will4/2-3/71/s2",)),
    ("land", "mortgage lender power of sale arrears", (f"{LPA25}/s101",)),
    ("land", "leasehold covenants pass on assignment new tenancies", ("uk/ukpga/1995/30/s3",)),
    # -- companies
    ("companies", "director duty avoid conflict of interest", (f"{CA06}/s175",)),
    ("companies", "director negligence standard reasonable care skill diligence", (f"{CA06}/s174",)),
    ("companies", "shareholder sues director on behalf of company derivative claim", (f"{CA06}/s260",)),
    ("companies", "minority shareholder unfairly prejudicial conduct petition", (f"{CA06}/s994",)),
    ("companies", "dividends only out of profits available for distribution", (f"{CA06}/s830",)),
    ("companies", "director service contract longer than two years member approval", (f"{CA06}/s188",)),
    ("companies", "director buys company asset substantial property transaction approval", (f"{CA06}/s190",)),
    ("companies", "register people with significant control company", (f"{CA06}/s790M",)),
    ("companies", "private company written resolution members", (f"{CA06}/s288",)),
    ("companies", "remove director ordinary resolution notice", (f"{CA06}/s168",)),
    ("companies", "public company financial assistance acquire own shares prohibited", (f"{CA06}/s678",)),
    ("companies", "company accounts filing deadline registrar private company", (f"{CA06}/s442",)),
    ("companies", "amend articles of association special resolution", (f"{CA06}/s21",)),
    ("companies", "articles bind company and members contract", (f"{CA06}/s33",)),
    ("companies", "unfit director disqualification insolvent company court order", (f"{CDDA}/s6",)),
    ("companies", "company name same as existing name registration", (f"{CA06}/s66",)),
    ("companies", "private company appoint auditor each financial year", (f"{CA06}/s485",)),
    # -- insolvency
    ("insolvency", "director continued trading knew no reasonable prospect avoiding insolvent liquidation", (f"{IA86}/s214",)),
    ("insolvency", "business carried on intent defraud creditors liquidator claim", (f"{IA86}/s213",)),
    ("insolvency", "company sold asset undervalue before liquidation set aside", (f"{IA86}/s238",)),
    ("insolvency", "paying one creditor ahead of others preference desire", (f"{IA86}/s239",)),
    ("insolvency", "grounds court winding up company unable pay debts", (f"{IA86}/s122",)),
    ("insolvency", "inability to pay debts statutory demand unpaid three weeks", (f"{IA86}/s123",)),
    ("insolvency", "administration moratorium creditors cannot enforce security", (f"{IA86}/schB1/para43",)),
    ("insolvency", "creditor bankruptcy petition debt threshold unsecured", (f"{IA86}/s267",)),
    ("insolvency", "bankrupt automatic discharge after one year", (f"{IA86}/s279",)),
    ("insolvency", "debtor individual voluntary arrangement proposal nominee", (f"{IA86}/s253", f"{IA86}/s256A")),
    ("insolvency", "employees wages preferential debts liquidation", (f"{IA86}/s386", f"{IA86}/sch6")),
    ("insolvency", "liquidator claim director breach of duty misfeasance", (f"{IA86}/s212",)),
    ("insolvency", "members resolution voluntary winding up", (f"{IA86}/s84",)),
    ("insolvency", "transactions defrauding creditors putting assets beyond reach", (f"{IA86}/s423",)),
    ("insolvency", "liquidator powers bring legal proceedings sell property", (f"{IA86}/s167", f"{IA86}/sch4")),
    # -- consumer and contract
    ("consumer_contract", "faulty goods consumer right repair or replacement", (f"{CRA15}/s23",)),
    ("consumer_contract", "consumer final right to reject price reduction", (f"{CRA15}/s24",)),
    ("consumer_contract", "downloaded software app digital content satisfactory quality", (f"{CRA15}/s34",)),
    ("consumer_contract", "trader service reasonable care and skill consumer", (f"{CRA15}/s49",)),
    ("consumer_contract", "unfair term consumer contract not binding", (f"{CRA15}/s62",)),
    ("consumer_contract", "exclude liability negligence death personal injury void", (f"{UCTA}/s2",)),
    ("consumer_contract", "exclusion clause business contract reasonableness test", (f"{UCTA}/s11", f"{UCTA}/s3")),
    ("consumer_contract", "third party enforce contract term purports confer benefit", (f"{CRTPA}/s1",)),
    ("consumer_contract", "seller right to sell goods implied term title", (f"{SGA}/s12",)),
    ("consumer_contract", "when property passes specific goods intention of parties", (f"{SGA}/s17",)),
    ("consumer_contract", "goods do not match description sale", (f"{SGA}/s13",)),
    ("consumer_contract", "online purchase cancel within fourteen days distance contract", ("uk/uksi/2013/3134/reg29", "uk/uksi/2013/3134/reg30")),
    ("consumer_contract", "damages negligent misrepresentation induced contract", (f"{MISREP}/s2",)),
    ("consumer_contract", "contract frustrated recover money paid before discharge", (f"{LRFCA}/s1",)),
    ("consumer_contract", "late payment commercial debt statutory interest", (f"{LPCDIA}/s1",)),
    ("consumer_contract", "defective product injury producer strict liability", (f"{CPA87}/s2",)),
    ("consumer_contract", "breach of contract claim six years limitation", (f"{LIMITATION}/s5",)),
    # -- data and information
    ("data_information", "request information public authority general right of access", (f"{FOIA}/s1",)),
    ("data_information", "freedom of information request refused cost exceeds limit", (f"{FOIA}/s12",)),
    ("data_information", "vexatious repeated information request refusal", (f"{FOIA}/s14",)),
    ("data_information", "information request third party personal data exemption", (f"{FOIA}/s40",)),
    ("data_information", "qualified exemption public interest balance disclosure", (f"{FOIA}/s2",)),
    ("data_information", "police processing personal data lawful fair first principle", (f"{DPA18}/s35",)),
    ("data_information", "information commissioner enforcement notice controller", (f"{DPA18}/s149",)),
    ("data_information", "data breach fine penalty notice maximum amount", (f"{DPA18}/s155", f"{DPA18}/s157")),
    ("data_information", "re-identifying anonymised personal data offence", (f"{DPA18}/s171",)),
    ("data_information", "unauthorised modification computer data impair operation", (f"{CMA90}/s3",)),
    ("data_information", "intercepting communications without lawful authority offence", (f"{IPA16}/s3",)),
    ("data_information", "unsolicited marketing email consent individual subscribers", (f"{PECR}/reg22",)),
    ("data_information", "environmental information request duty make available", (f"{EIR}/reg5",)),
    ("data_information", "compensation distress data protection contravention claim", (f"{DPA18}/s168", f"{DPA18}/s169")),
    ("data_information", "law enforcement right erasure restriction processing", (f"{DPA18}/s47",)),
    # -- family and children
    ("family", "child's welfare paramount court upbringing decision", (f"{CHA89}/s1",)),
    ("family", "unmarried father parental responsibility acquire", (f"{CHA89}/s4",)),
    ("family", "court order who child lives with spends time with", (f"{CHA89}/s8",)),
    ("family", "care order threshold child suffering significant harm", (f"{CHA89}/s31",)),
    ("family", "emergency protection order remove child immediate danger", (f"{CHA89}/s44",)),
    ("family", "local authority investigate child suspected harm enquiries", (f"{CHA89}/s47",)),
    ("family", "no fault divorce application marriage broken down irretrievably", (f"{MCA73}/s1",)),
    ("family", "divorce lump sum periodical payments financial orders", (f"{MCA73}/s23",)),
    ("family", "factors court considers dividing assets divorce", (f"{MCA73}/s25",)),
    ("family", "dependant claim estate reasonable financial provision will", (f"{IPFDA}/s1",)),
    ("family", "will signed two witnesses formal validity", (f"{WILLS}/s9",)),
    ("family", "marriage revokes existing will", (f"{WILLS}/s18",)),
    ("family", "non-molestation order domestic violence", (f"{FLA96}/s42",)),
    ("family", "occupation order family home exclude partner", (f"{FLA96}/s33",)),
    ("family", "adoption decision child's welfare throughout life paramount", (f"{ACA02}/s1",)),
    ("family", "definition domestic abuse controlling coercive behaviour", (f"{DAA21}/s1",)),
    ("family", "lasting power of attorney appoint attorney decisions", (f"{MCA05}/s9",)),
    ("family", "person presumed to have capacity unless established otherwise", (f"{MCA05}/s1",)),
    # -- tax
    ("tax", "income tax personal allowance amount individuals", (f"{ITA07}/s35",)),
    ("tax", "capital gains annual exempt amount individuals", (f"{TCGA}/s1K",)),
    ("tax", "selling main home private residence relief capital gains", (f"{TCGA}/s222", f"{TCGA}/s223")),
    ("tax", "company car benefit in kind employee taxable", (f"{ITEPA}/s114",)),
    ("tax", "termination payment first £30,000 exempt", (f"{ITEPA}/s403",)),
    ("tax", "inheritance tax nil rate band threshold", (f"{IHTA}/s7", f"{IHTA}/sch1")),
    ("tax", "gift survives seven years potentially exempt transfer", (f"{IHTA}/s3A",)),
    ("tax", "business must register for VAT turnover threshold", (f"{VATA}/sch1",)),
    ("tax", "stamp duty land tax chargeable land transaction", (f"{FA03}/s42",)),
    ("tax", "corporation tax charged on company profits", (f"{CTA09}/s2",)),
    ("tax", "general anti-abuse rule abusive tax arrangements", (f"{FA13}/s206",)),
    ("tax", "HMRC penalty careless inaccuracy tax return", (f"{FA07}/sch24",)),
    ("tax", "HMRC enquiry into self assessment return notice", (f"{TMA}/s9A",)),
    ("tax", "HMRC discovery assessment loss of tax time limits", (f"{TMA}/s29", f"{TMA}/s34", f"{TMA}/s36")),
    ("tax", "statutory residence test UK resident individual", (f"{FA13}/sch45",)),
    ("tax", "income tax charged on profits of a trade", (f"{ITTOIA}/s5",)),
    ("tax", "dividend income charged to income tax", (f"{ITTOIA}/s383",)),
]
# fmt: on

D0_PROBE_QUERIES: Final = (
    "unfair dismissal compensatory award statutory cap",
    "unfair dismissal compensation cap",
    "redundancy payment maximum statutory limit",
    "time off ante-natal care",
    "dishonest appropriation property another permanently deprive",
    "disability reasonable adjustments employer duty",
    "data subject right of access personal data",
    "assured shorthold tenancy possession notice landlord",
    "limitation period personal injury three years",
    "whistleblowing protected disclosure detriment",
    "grievous bodily harm with intent",
    "director duty promote success of company",
    "implied term satisfactory quality goods consumer",
    "flexible working request statutory right",
    "minimum notice period termination employment",
)
"""The D0 evidence probe's queries (docs/discovery.md): kept out of the battery, never tuned on."""
