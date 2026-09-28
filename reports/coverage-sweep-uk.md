# Coverage sweep (UK)

Index: `full UK index (Stage B, snapshot 2026-09-28)`. Citations swept: 100000 (the `sweep` side of the harvest split; 20 % is held out for the misroute battery and never swept). Quoted source text: legislation.gov.uk, Crown copyright, Open Government Licence v3.0.

| Outcome | Count | Share |
|---|---|---|
| correct | 80015 | 80.02 % |
| miss | 8553 | 8.55 % |
| false_abstention | 6470 | 6.47 % |
| ambiguous | 4281 | 4.28 % |
| out_of_coverage | 566 | 0.57 % |
| dropped | 99 | 0.10 % |
| wrong_provision | 9 | 0.01 % |
| misroute | 7 | 0.01 % |

`misroute`: the router read the cited text and bound another instrument. `dropped`: it bound other citations in the same clause and never recognised this one.

## Most frequent missed citation shapes

| Shape | Count |
|---|---|
| `N/N` | 6923 |
| `N/N (c. N)` | 375 |
| `N/N (c.N)` | 250 |
| `N` | 203 |
| `N/N (w.N)` | 167 |
| `N (c. N)` | 103 |
| `N/N (w. N)` | 97 |
| `N/N (w. N) (c. N)` | 74 |
| `N/N (w.N) (c.N)` | 54 |
| `subsection (N)` | 43 |
| `N (c.N)` | 32 |
| `(N)` | 19 |
| `N/N(c.N)` | 17 |
| `N/N (w.N)(c.N)` | 15 |
| `paragraph N` | 15 |
| `paragraph (N)` | 10 |
| `sub-paragraph (N)` | 9 |
| `N. c.N` | 8 |
| `paragraph (b)` | 7 |
| `paragraph (a)` | 7 |
| `c.N` | 6 |
| `(a)` | 5 |
| `N. c. N` | 5 |
| `N/N (s. N)` | 4 |
| `(c.N)` | 4 |
| `o.s. N/N` | 4 |
| `c. N` | 4 |
| `(i)` | 4 |
| `N/N (cN)` | 3 |
| `that section` | 3 |
| `s.i. N/N` | 3 |
| `s.N.N/N (c.N)` | 3 |
| `(c)` | 2 |
| `paragraph (c)` | 2 |
| `paragraph (e)` | 2 |
| `N c .N` | 2 |
| `paragraph (d)` | 2 |
| `N/N (w. N) (c.N)` | 2 |
| `section Neza` | 2 |
| `N p.N` | 2 |

## Examples: misroute

| Citation | Query (source text) | Target |
|---|---|---|
| `The Town and Country Planning (Environme` | The Town and Country Planning (Environmental Impact Assessment) Regulations 2017 (S.I. 2018/1232), regs. 1(2), 6(11)(b) | `uk/uksi/2017/1232` |
| `1972 c. 68` | 1972 c. 68 | `uk/uksi/1972/68` |
| `1094` | S.I. 2015/137, 570, 1862 and 1879, 2016/696 and 1077, 2018/1114, 2019/593, 990 and 1094, 2020/351 and 1126, and 2021/169. | `uk/uksi/2015/1094` |
| `694` | amending instruments are S.I. 2001/1700, 2005/2114, 2006/752, 2910, 2007/1025, 2009/1182, 2010/231, 2012/1479, 2013/388, 591, 3198, 2015/643, 1971, 2016/211, 694, 2017/52, 2018/48, 1310 and 2020/1399 (W. 310). | `uk/uksi/2015/694` |
| `1171` | S.I. 2020/1527, 2021/136, 426, 641, 1229 and 1171. | `uk/uksi/2020/1171` |
| `The Nursing and Midwifery Order 2001 (S.` | The Nursing and Midwifery Order 2001 (S.I. 2002/253), art. 54(3), Sch. 5 para. 17(a) (with art. 3(18)) | `uk/uksi/2001/253` |
| `The National Health Service (General Med` | The National Health Service (General Medical Services Contracts and Personal Medical Services Agreements) (Amendment) (No. 2) Regulations 2023 (S.I. 2023/449), reg. 1(2), Sch. 2 para. 6(2) | `uk/uksi/2023/436` |

## Examples: dropped

| Citation | Query (source text) | Target |
|---|---|---|
| `2022/346` | 2010/2914, 2011/721, 2013/591, 2014/513, 2016/360, 2016/978, 2018/365, 2019/364, 2020/297, 2020/534, 2020/941, 2020/1515, 2021/495, 2021/810, 2021/1286 and 2022/346 and S.I. 2004/1748 (W. 185). | `uk/uksi/2022/346` |
| `2008/1911` | 2008/1911, amended by S.I. 2009/1342, 2009/1804, 2011/99, 2011/1043, 2012/1439, 2012/1741, 2012/2301, 2013/472, 2013/2005, | `uk/uksi/2008/1911` |
| `2023/301` | S.I. 2022/991), 2023/301, 2023/576 and 2024/281. | `uk/uksi/2023/301` |
| `1985/1625` | S.I. 1974/506, relevant amending instruments are 1975/696, 1982/1279, 1985/1625, 1989/1883, 1989/1990, 1991/572, 1992/191, 1993/521. | `uk/uksi/1985/1625` |
| `2010/22` | relevant amending instruments are S.I. 2006/563, 2007/544, 2008/528, 2009/4622010/22, 2011/1182, 2012/2273, 2013/364, 2014/443, 2015/1728, 2016/298, 2017/1056, 2020/351, 2022/1132, 2023/1071 and 2026/265. | `uk/uksi/2010/22` |
| `1991/1175` | Relevant amending instruments are S.I. 1988/1971, 1990/127and 1775, 1991/1175and 1599and 1992/1101. | `uk/uksi/1991/1175` |
| `2000/2267` | relevant amending instruments are S.I. 1991/2113, 1992/456, 1992/20671993/295, 1994/3155, 1996/816, 1997/1056, 1998/1901, 2000/2267, 2001/821, 2003/184, 2003/2839, 2004/3375, 2005/264, 2005/412, 2005/559 and 2005/1976. | `uk/uksi/2000/2267` |
| `1990/2495` | S.I. 1990/2486, 1990/2494 and1990/2495. | `uk/uksi/1990/2495` |
| `2011/1182` | relevant amending instruments are S.I. 2006/563, 2007/544, 2008/528, 2009/4622010/22, 2011/1182, 2012/2273, 2013/364, 2014/443, 2015/1728, 2016/298, 2017/1056, 2020/351, 2022/1132, 2023/1071 and 2026/265. | `uk/uksi/2011/1182` |
| `S.I. 1984` | S.I. 1984, as amended by section 52 of the Criminal Justice Act 1988 (1988 c. 33), S.I. 1990/2371 and 2486 and S.I. 1996/3124 | `uk/uksi/1984/1918` |
| `2021/1452` | S.I. 2020/1488), 2021/1452 and 2024/832. | `uk/uksi/2021/1452` |
| `c.36` | c.36. as amended by section 1(2) of the Nurses, Midwives and Health Visitors Act 1992 (c. 16). | `uk/ukpga/1979/36` |
| `2005/412` | are S.I. 1991/2113, 1992/456, 1992/20671993/295, 1994/3155, 1996/816, 1997/1056, 1998/1901, 2000/2267, 2001/821, 2003/184, 2003/2839, 2004/3375, 2005/264, 2005/412, 2005/559 and 2005/1976. | `uk/uksi/2005/412` |
| `1997/2817` | 1997/2817 as amended by S.I. 1998/669. | `uk/uksi/1997/2817` |
| `2003/1690` | relevant amending instruments are S.I. 1995/2210, 1996/2085 1997/1544, 1998/1563, 1999/1521, 1999/1959, 2000/1434, 2001/1825, 2002/1474 and 2003/1690. | `uk/uksi/2003/1690` |

## Examples: wrong_provision

| Citation | Query (source text) | Target |
|---|---|---|
| `Part 3` | “street works permit” means a permit granted pursuant to a permit scheme prepared under Part 3 of the Traffic Management Act 2004. | `uk/ukpga/2004/18/pt3` |
| `Part 3` | “special post-16 institution” has the same meaning as in Part 3 of the Children and Families Act 2014 (see section 83 of that Act) | `uk/ukpga/2014/6/pt3` |
| `(10)` | sections 15 (2) and (3), 17 and 240 (10) of the Local Government and Public Involvement in Health Act 2007. | `uk/ukpga/2007/28/s240` |
| `Part 10` | Part 10 of ITEPA 2003 (social security income) is amended as follows. | `uk/ukpga/2003/1/pt10` |
| `Part 7` | In this regulation “disciplinary penalty” has the same meaning as in Chapter 1 of Part 7 of the Education and Inspections Act 2006. | `uk/ukpga/2006/40/pt7` |
| `Part 8` | or similar to, or applying (with or without modification), any provision of Part 10 of the Merchant Shipping Act 1995 (enforcement officers and powers) or Part 8 of the Marine and Coastal Access Act 2009 (enforcement). | `uk/ukpga/2009/23/pt8` |
| `Part 4` | “registered pension scheme” has the meaning given in Part 4 of the Finance Act 2004 | `uk/ukpga/2004/12/pt4` |
| `Part 1` | In subsection (1)(b), “general customs function” has the same meaning as in Part 1 of the Borders, Citizenship and Immigration Act 2009 (see section 1(8) of that Act). | `uk/ukpga/2009/11/pt1` |
| `Part 2` | Part 2 of the Education and Inspections Act 2006 (establishment, discontinuance or alteration of schools) is amended as | `uk/ukpga/2006/40/pt2` |

## Examples: false_abstention

| Citation | Query (source text) | Target |
|---|---|---|
| `S.I. 2010/2279` | S.I. 2010/2279, Sch. 2) (with ss. 6(4), 205, and with amendments and savings in the said S.I. 2010/2279, art. 16) | `uk/uksi/2010/2279` |
| `Local Government Finance Act 1992 (c. 14` | Schedule 9 to the Local Government Finance Act 1992 (c. 14), paragraphs 1(1) and 9 | `uk/ukpga/1992/14` |
| `The Greater Manchester Combined Authorit` | The Greater Manchester Combined Authority (Functions and Amendment) Order 2017 (S.I. 2017/612), arts. 1(3), 4(1)(2), Sch. | `uk/uksi/2017/612` |
| `2020 c. 1` | Reg. 8 in force at 31.12.2020 immediately before IP completion day (in accordance with 2020 c. 1, Sch. 5 para. 1(1)), see reg. 1(2) | `uk/ukpga/2020/1` |
| `S.I.1991/993` | See article 21 of S.I.1966/982, article 21 S.I.1973/2135, article 15 of S.I.1988/1519, article 24 of S.I.1991/993, article 21 of S.I.1993/2733 and article 23 of S.I.1994/2733. | `uk/uksi/1991/993` |
| `Merchant Shipping Act 1970 (c. 36)` | Merchant Shipping Act 1970 (c. 36), s. 100(3), Sch. 5 (with Sch. 4) | `uk/ukpga/1970/36` |
| `S.I. 2001/544` | the Contracts (Applicable Law) Act 1990 (c.36), section 5 and Schedule 4, paragraph 2, the Consumer Credit Act 2006, Schedule 4, and S.I. 2001/544. | `uk/uksi/2001/544` |
| `Taxation of Chargeable Gains Act 1992 (c` | Taxation of Chargeable Gains Act 1992 (c. 12), ss. 289, 290, Sch. 10 para. 14(63)(b) (with ss. 60, 101(1), 171, 201(3)) | `uk/ukpga/1992/12` |
| `2004 (c.34)` | 3 to the Housing Act 1996, S.I.1996/2325 and section 218 of, and paragraph 1 of Schedule 11 to, and section 266 of, and Schedule 18 to the Housing Act 2004 (c.34). | `uk/ukpga/2004/34` |
| `2020 c. 1` | Reg. 122 in force at 31.12.2020 on IP completion day (in accordance with 2020 c. 1, Sch. 5 para. 1(1)), see reg. 1 | `uk/ukpga/2020/1` |
| `2020 c. 1` | Reg. 6 in force at 31.12.2020 on IP completion day (in accordance with 2020 c. 1, Sch. 5 para. 1(1)), see reg. 1(4)(a) | `uk/ukpga/2020/1` |
| `2005 (c. 9)` | section 58(2A) of the Mental Capacity Act 2005 (c. 9) (the “2005 Act”), as inserted by section 17(2) of the Guardianship (Missing Persons) Act 2017 (c. 27) (“the 2017 Act”). | `uk/ukpga/2005/9` |
| `Welfare Reform and Pensions Act 1999 (c.` | section 57 of the Welfare Reform and Pensions Act 1999 (c. 30) and amended by section 53 of, and paragraphs 8 and 9 of Schedule 7 to, and section 54 of, and Schedule 8 to, the | `uk/ukpga/1999/30` |
| `2020 c. 1` | Reg. 110 in force at 31.12.2020 on IP completion day (in accordance with 2020 c. 1, Sch. 5 para. 1(1)), see reg. 1 | `uk/ukpga/2020/1` |
| `S.I. 1991/2721` | S. 15 wholly in force at 6.1.1992 see ss. 1(1), 18(2) and S.I. 1991/2721, art.2 | `uk/uksi/1991/2721` |

## Examples: miss

| Citation | Query (source text) | Target |
|---|---|---|
| `2022/1075` | 2022/1075 | `uk/uksi/2022/1075` |
| `2004/1728 (W.172)` | 2004/1728 (W.172) | `uk/wsi/2004/1728` |
| `O.S. 1980 Rhif 1697` | O.S. 1980 Rhif 1697. | `uk/uksi/1980/1697` |
| `2005/275` | 2005/275 | `uk/uksi/2005/275` |
| `2009/1606` | 2009/1606 | `uk/uksi/2009/1606` |
| `2009/1606` | 2009/1606 | `uk/uksi/2009/1606` |
| `2004/759` | 2004/759 | `uk/uksi/2004/759` |
| `2009/462 (C. 31)` | 2009/462 (C. 31) | `uk/uksi/2009/462` |
| `2014/1583` | 2014/1583 | `uk/uksi/2014/1583` |
| `2000/1985` | 2000/1985 | `uk/uksi/2000/1985` |
| `2001/3150` | 2001/3150 | `uk/uksi/2001/3150` |
| `2007/709` | 2007/709 | `uk/uksi/2007/709` |
| `2005/1909` | 2005/1909 | `uk/uksi/2005/1909` |
| `2011/2054` | 2011/2054 | `uk/uksi/2011/2054` |
| `2008/3244 (C. 148)` | 2008/3244 (C. 148) | `uk/uksi/2008/3244` |

## Examples: ambiguous

| Citation | Query (source text) | Target |
|---|---|---|
| `The School Discipline (Pupil Exclusions ` | The School Discipline (Pupil Exclusions and Reviews) (England) (Amendment and Transitional Provision) Regulations 2023 (S.I. 2023/571), regs. 1(1), 12(4) (with regs. 1(3), 16) (as amended by S.I. 2023/882, regs. 1(2), 4, | `uk/uksi/2023/571` |
| `S.I.2002/1419` | the Deregulation (Correction of Births and Death Entries in Registers or other Records) Order 2002 (S.I.2002/1419) article 2(1) | `uk/uksi/2002/1419` |
| `S.I. 2014/956` | S.I. 2014/954, art. 2(e) (with art. 3) (with transitional provisions and savings in S.I. 2014/956, arts. 3-11) | `uk/uksi/2014/956` |
| `S.I. 2024/153` | Partnerships) Regulations 2012 (S.I. 2012/1907) (“the 2012 Regulations”), the Registrar of Companies (Fees) (Register of Overseas Entities) Regulations 2024 (S.I. 2024/153) (“the 2024 Regulations”), the Registrar of Comp | `uk/uksi/2024/153` |
| `S.I. 1998/2327` | S.I. 1998/2327, art. 3(1)(b), Sch. 1 (with art. 9) (which Sch. 8 para. 27 of the 1998 c. 37 is repealed by 2000 c. 6, ss. 165, 168, | `uk/uksi/1998/2327` |
| `S.I. 2002/1792` | Support (General) Regulations 1987 (S.I. 1987/1967), the Jobseeker’s Allowance Regulations 1996 (S.I. 1996/207), the State Pension Credit Regulations 2002 (S.I. 2002/1792), the Housing Benefit Regulations 2006 (S.I. 2006 | `uk/uksi/2002/1792` |
| `2009 (c. 22)` | Schedule 8, paragraphs 1, 13(1), (3) of the Apprenticeship, Skills, Children and Learning Act 2009 (c. 22). | `uk/ukpga/2009/22` |
| `2001/3852` | 20022001/3852Section 6(3) and Schedule 1 (partially)16th March 20012001/1193Section 6 and Schedule 1 (partially)9th April 20012001/1193Section 71st April 20022001/3852Section 10 (partially)1st April 20022001/3852Section  | `uk/uksi/2001/3852` |
| `Finance Act 2024 (c. 3)` | Finance Act 2024 (c. 3), Sch. 9 paras. 40(3)(c)(i), 124 (with Sch. 9 paras. 125-132 (as amended (18.11.2024 for the tax year 2024-25 and | `uk/ukpga/2024/3` |
| `Taxation (Cross-border Trade) Act 2018 (` | Taxation (Cross-border Trade) Act 2018 (c. 22), s. 57(3), Sch. 8 para. 23(4)(a) (with Sch. 8 para. 99) (with savings and transitional provisions in S.I. 2019/105 (as | `uk/ukpga/2018/22` |
| `1991 (c. 22)` | section 102 of, and Schedule 17 to, the Local Government Act 1985 (c. 51) and section 168(2) of, and Schedule 9 to, the New Roads and Street Works Act 1991 (c. 22). | `uk/ukpga/1991/22` |
| `1996/3215` | Court and County Courts Jurisdiction Order 1991, S.I. 1991/724, and the High Court and County Courts (Allocation of Arbitration Proceedings) Order 1996, S.I. 1996/3215, enable applications under section 26 of the Arbitra | `uk/uksi/1996/3215` |
| `section 13` | section 13 (offences involving threats). | `uk/ukpga/1990/31/s13` |
| `(1)` | “request to pay” means a request to pay the levy under section 72 (1) of the 2025 Act | `uk/ukpga/2025/34/s72` |
| `2015 (c. 2)` | the Legal Aid, Sentencing and Punishment of Offenders Act 2012 (c. 10), section 28 of, and paragraph 2 of Schedule 5 to, the Criminal Justice and Courts Act 2015 (c. 2) and section 416 of, and paragraphs 89 and 267 of Sc | `uk/ukpga/2015/2` |

## Reading this report (hand-written, 28 Sept 2026)

Generated by `uv run python -m eval.sweep run --harvest data/harvest/uk_citations.jsonl --index data/index --sample 100000 --out reports/coverage-sweep-uk.md` over the full Stage B index (133,798 instruments, 5.7M coordinates). The sample is drawn with the fixed seed from the 1,378,692 eligible `sweep` citations. Every query is the clause of the source text that holds the citation (`eval.sweep.replay_query`), so each row is a citation written by a drafter, not by us.

What the buckets hold, from inspecting them:

- **misroute (7):** 6 are errors in the source's own link target: the text is read correctly and the `<Citation>` URI is wrong. Examples: "1972 c. 68" linked to an SI; "The Nursing and Midwifery Order 2001 (S.I. 2002/253)" linked to 2001/253; "S.I. 2023/449" linked to 2023/436; list items linked to the wrong year. 1 is a real conflict: "…Regulations 2017 (S.I. 2018/1232)", where the title and the number name different SIs and both are bound (open question in the roadmap).
- **dropped (99):** list items the router never recognised while binding the rest of the clause. They are source typos ("2009/4622010/22", "1990/127and 1775"), replay windows that cut off the "S.I." cue, or list items after an outer closing bracket ("(… S.I. 2022/991), 2023/301").
- **miss (8,553):** 7,459 are bare `yyyy/n` cells from commencement tables, with or without a series note ("2008/3244 (C. 148)") and with no "S.I." cue. That is a documented unsupported form (grammar.md UK-U-05). Most of the rest are the same tables' cells holding a number alone ("963", "963 (C. 41)") under a year row. About a hundred are relative references ("subsection (2)", "paragraph (a)", "that section"), UK-U-02.
- **false_abstention (6,470):** mostly provisions the current text no longer has (repealed articles whose text is dots, subsections removed by amendment). By decision 19 these get a plain refusal. Also savings provisions cited in "(with …)", and host provisions linked across annotation prose ("Reg. 8 in force … (in accordance with 2020 c. 1, …)").
- **ambiguous (4,281):** includes the intended questions: `year_only`, `title_number_conflict`, `provision_without_instrument` and `duplicated_in_source`.

Stage A (partial data, 20,000 citations) is kept in `coverage-sweep-uk-stageA.md` for comparison. Its sample held few SIs, because few were downloaded then.
