# Coverage sweep (UK)

Index: `Stage A partial UK index (snapshot 2026-09-27, 33,788 scraped files; sample of 20,000)`. Citations swept: 20000 (the `sweep` side of the harvest split; 20 % is held out for the misroute battery and never swept). Quoted source text: legislation.gov.uk, Crown copyright, Open Government Licence v3.0.

| Outcome | Count | Share |
|---|---|---|
| correct | 17145 | 85.72 % |
| false_abstention | 1551 | 7.75 % |
| ambiguous | 644 | 3.22 % |
| out_of_coverage | 431 | 2.15 % |
| miss | 225 | 1.12 % |
| wrong_provision | 3 | 0.01 % |
| misroute | 1 | 0.01 % |

## Most frequent missed citation shapes

| Shape | Count |
|---|---|
| `N/N` | 73 |
| `subsection (N)` | 34 |
| `N (c. N)` | 20 |
| `paragraph (a)` | 11 |
| `paragraph N` | 8 |
| `paragraph (b)` | 7 |
| `(N)` | 6 |
| `sub-paragraph (N)` | 6 |
| `N/N (c. N)` | 5 |
| `N (c.N)` | 4 |
| `(b)` | 3 |
| `N` | 3 |
| `(a)` | 3 |
| `paragraph Na` | 2 |
| `schedule N` | 2 |
| `section N` | 2 |
| `ittoia N` | 2 |
| `that sub-paragraph` | 2 |
| `section Nza` | 2 |
| `subsections (N)` | 2 |
| `N/N (w. N)` | 2 |
| `section Na` | 2 |
| `that paragraph` | 2 |
| `(Nb)` | 1 |
| `sections N` | 1 |
| `that section` | 1 |
| `itepa N` | 1 |
| `(i)` | 1 |
| `section Nc` | 1 |
| `subsections (N) to (N)` | 1 |
| `subsection (Nab)` | 1 |
| `paragraph (h)` | 1 |
| `f(no.N)a N` | 1 |
| `N p.N` | 1 |
| `N/N (w.N)` | 1 |
| `section Nzza` | 1 |
| `N (c N)` | 1 |
| `paragraph Nzl` | 1 |
| `(ba)` | 1 |
| `subsection (Na)` | 1 |

## Examples: misroute

| Citation | Query (source text) | Target |
|---|---|---|
| `(3A)` | In section 33(3A) (inserted by section 18 of the Victims and Prisoners Act 2024)— | `uk/ukpga/1989/41/s33` |

## Examples: wrong_provision

| Citation | Query (source text) | Target |
|---|---|---|
| `Part 4` | Schedule 2 amends Chapter 3 of Part 4 of the Anti-social Behaviour, Crime and Policing Act 2014 so as to enable registered social housing providers to close | `uk/ukpga/2014/12/pt4` |
| `Part 7` | or under Chapter 6 of Part 7 of the Online Safety Act 2023 in relation to enforceable requirements, including provisions conferring power to impose | `uk/ukpga/2023/50/pt7` |
| `Part 3` | “street works permit” means a permit granted pursuant to a permit scheme prepared under Part 3 of the Traffic Management Act 2004 | `uk/ukpga/2004/18/pt3` |

## Examples: false_abstention

| Citation | Query (source text) | Target |
|---|---|---|
| `1992 c. 4` | 1992 c. 4, s. 11A (as inserted (with effect in accordance with Sch. 1 para. 35 of the amending Act) by National Insurance | `uk/ukpga/1992/4` |
| `Family Law Reform Act 1969 (c. 46)` | Intestates' Estates Act 1952 (c. 64), s. 6(2) and Family Law Reform Act 1969 (c. 46), s. 14(6). | `uk/ukpga/1969/46` |
| `1994 c. 19` | 1994 c. 19, ss. 39, 66(2)(b), Sch. 13 para. 23(b) (with ss. 54(5)(7), 55(5), Sch. 17 paras. 22(1), 23(2)) | `uk/ukpga/1994/19` |
| `Drug Trafficking Offences Act 1986 (c.32` | Drug Trafficking Offences Act 1986 (c.32, SIF 39:1), s. 10(2) | `uk/ukpga/1986/32` |
| `2000 c. 23` | 2000 c. 23, s. 82(1), Sch. 4 para. 82(3) | `uk/ukpga/2000/23` |
| `See Finance Act 1984 (c. 43, SIF 63:1)` | See Finance Act 1984 (c. 43, SIF 63:1), s. 50(1) and Sch. 11 para. 1 | `uk/ukpga/1984/43` |
| `Transport Act 1985 (c. 67, SIF 126)` | Transport Act 1985 (c. 67, SIF 126), ss. 57(6), 139(3), Sch. 3 para. 14(a), Sch. 8 | `uk/ukpga/1985/67` |
| `2013 (c.29)` | Finance Act 2004 (c.12), section 16(3) of, and paragraphs 24 and 25 of Schedule 6 to, the Finance Act 2008 (c.9) and section 179(1) and (4) of the Finance Act 2013 (c.29). | `uk/ukpga/2013/29` |
| `1987 (c.42)` | section 25 of the Family Law Reform Act 1987 (c.42), was amended by 2008 (c. 22), section 56 and Schedule 6, paragraph 7. | `uk/ukpga/1987/42` |
| `Environmental Protection Act 1990 (c. 43` | Environmental Protection Act 1990 (c. 43, SIF 46:4), s. 100(2) | `uk/ukpga/1990/43` |
| `Roads (Scotland) Act 1984 (c. 54, SIF 10` | Roads (Scotland) Act 1984 (c. 54, SIF 108), Sch. 9 para. 39(18)(a) | `uk/ukpga/1984/54` |
| `Northern Ireland Constitution Act 1973 (` | Secretary of State: Irish Free State (Consequential Provisions) Act 1922 (13 Geo. 5 Sess. 2 c. 2), Sch. 1 para. 1(1) and Northern Ireland Constitution Act 1973 (c. 36), Sch. 5 para. 4 | `uk/ukpga/1973/36` |
| `2002 (c. 17)` | and the National Health Service Reform and Health Care Professions Act 2002 (c. 17) (“the 2002 Act”), Schedule 2, paragraph 2(2) | `uk/ukpga/2002/17` |
| `Sea Fish Industry Act 1970 (c. 11)` | Sea Fisheries (Shellfish) Act 1967 (c. 83), Sch. 3, Sea Fish (Conservation) Act 1967 (c. 84), Sch. and Sea Fish Industry Act 1970 (c. 11), Sch. 6 Pt | `uk/ukpga/1970/11` |
| `1982 (c. 48)` | section 49(3) of the Criminal Justice Act 1982 (c. 48). | `uk/ukpga/1982/48` |

## Examples: miss

| Citation | Query (source text) | Target |
|---|---|---|
| `2001/1252` | 2001/1252 | `uk/uksi/2001/1252` |
| `paragraph 5A` | Omit paragraph 5A (consideration of proposals: distinction between Academy and non-Academy proposals). | `uk/ukpga/2006/40/sch2/para5A` |
| `1989/1117` | 1989/1117 | `uk/uksi/1989/1117` |
| `2004/2202` | 2004/2202 | `uk/uksi/2004/2202` |
| `2004/2523` | 2004/2523 | `uk/uksi/2004/2523` |
| `subsection (2)` | in subsection (2)(a), omit “, with the consent of the Secretary of State” | `uk/ukpga/2006/40/s7A` |
| `(2B)` | for subsections (2A) and (2B) substitute— | `uk/ukpga/1983/20/s1` |
| `Schedule 41` | In paragraph 1 of Schedule 41 to FA 2008 (penalties for failure to notify etc), in the table after the entry for tobacco products duty insert— | `uk/ukpga/2008/9/sch41` |
| `2005/2896 (C. 122)` | 2005/2896 (C. 122) | `uk/uksi/2005/2896` |
| `1994 (c. 5)` | 1994 (c. 5) | `uk/ukpga/1994/5` |
| `2000/2156` | 2000/2156 | `uk/uksi/2000/2156` |
| `1990 (c. 43)` | 1990 (c. 43) | `uk/ukpga/1990/43` |
| `section 71` | In section 71(2)(a)(i) (duty not to take down content except in accordance with terms of service: exceptions) for “or (3)” | `uk/ukpga/2023/50/s71` |
| `sections 445` | In sections 445(1), 446 and 447(1) and (2)(a), for “443” substitute “436Q”. | `uk/ukpga/1996/56/s445` |
| `(b)` | omit paragraphs (a) and (b) | `uk/ukpga/1992/52/s193` |

## Examples: ambiguous

| Citation | Query (source text) | Target |
|---|---|---|
| `1979 (c. 4)` | This Order brings into force the amendments to the Alcoholic Liquor Duties Act 1979 (c. 4) made by section 4 of the Finance Act 2004 (c. 12) in relation to retail containers containing alcoholic liquor if the | `uk/ukpga/1979/4` |
| `1990 (c.16)` | regulation 10 of the 1998 Regulations in relation to offences and penalties and the application and modification of certain sections of the Food Safety Act 1990 (c.16) | `uk/ukpga/1990/16` |
| `2003 (c. 39)` | section 65 of, and paragraph 6 of Schedule 4 to, the Courts Act 2003 (c. 39) and section 113 of the Serious Organised Crime and Police Act 2005 (c. 15). | `uk/ukpga/2003/39` |
| `Capital Transfer Tax Act 1984 (c. 51, SI` | Capital Transfer Tax Act 1984 (c. 51, SIF 65), ss. 274, 277, schs, 7, 9 | `uk/ukpga/1984/51` |
| `S.I. 2010/303` | S.I. 2010/303, art. 4, Sch. 3 (with arts. 8-14) (as amended by S.I. 2010/1151, art. 22) | `uk/uksi/2010/303` |
| `1972 c. 70` | 1972 c. 70, to which there are amendments not relevant to this Order | `uk/ukpga/1972/70` |
| `2007 (c.22)` | section 18 of the Pensions Act 2007 (c.22) and section 124 of the Pensions Act 2008 and is modified in its application to multi-employer schemes by regulation 76 | `uk/ukpga/2007/22` |
| `2004 c. 12` | 2004 c. 12, Sch. 36 para. 29A (as inserted by Finance Act 2024 (c. 3), Sch. 9 paras. 85, 124 (with Sch. 9 paras. 125-132A) (as | `uk/ukpga/2004/12` |
| `Taxation (Cross-border Trade) Act 2018 (` | Taxation (Cross-border Trade) Act 2018 (c. 22), s. 57(3), Sch. 8 para. 43 (with Sch. 8 para. 99) (with savings and transitional provisions in S.I. 2019/105 (as | `uk/ukpga/2018/22` |
| `1999 c. 14` | section 8 of the Protection of Children Act 1999 c. 14 and amended by sections 104, 106 and 116 of, and paragraph 25 of Schedule 4 to, the Care Standards Act 2000. | `uk/ukpga/1999/14` |
| `The Payment and Electronic Money Institu` | The Payment and Electronic Money Institution Insolvency Regulations 2021 (S.I. 2021/716), regs. 2, 37 (with reg. 5) (as amended (4.1.2024) by S.I. 2023/1399, regs. 1(2), 4, 11) | `uk/uksi/2021/716` |
| `1993 (c. 34)` | Part IV of Schedule 19 to the Finance Act 1990 (c. 29), section 107(3) of, and Part III(10) of Schedule 23 to, the Finance Act 1993 (c. 34), and section 25(3) of the Finance Act 1999 (c. 16). | `uk/ukpga/1993/34` |
| `S.I. 1992/334` | S.I. 1992/334, art.4 and S.I. 1992/1937, art. 4 (with art. 5). | `uk/uksi/1992/334` |
| `Taxation (Cross-border Trade) Act 2018 (` | Taxation (Cross-border Trade) Act 2018 (c. 22), s. 57(3), Sch. 8 para. 89(2)(b) (with Sch. 8 para. 99) (with savings and transitional provisions in S.I. 2019/105 (as | `uk/ukpga/2018/22` |
| `Finance Act 2024 (c. 3)` | Finance Act 2024 (c. 3), Sch. 9 paras. 61(3)(b), 124 (with Sch. 9 paras. 125-132 (as amended (18.11.2024 for the tax year 2024-25 and | `uk/ukpga/2024/3` |
