# Coverage sweep (UK)

Index: `full UK index (Stage B, snapshot 2026-09-28)`. Citations swept: 100000 (the `sweep` side of the harvest split; 20 % is held out for the misroute battery and never swept). Quoted source text: legislation.gov.uk, Crown copyright, Open Government Licence v3.0.

| Outcome | Count | Share |
|---|---|---|
| correct | 80024 | 80.02 % |
| miss | 8541 | 8.54 % |
| false_abstention | 6333 | 6.33 % |
| ambiguous | 4371 | 4.37 % |
| out_of_coverage | 612 | 0.61 % |
| dropped | 107 | 0.11 % |
| misroute | 7 | 0.01 % |
| wrong_provision | 5 | 0.01 % |

`misroute`: the router read the cited text and bound another instrument. `dropped`: it bound other citations in the same clause and never recognised this one.

## Most frequent missed citation shapes

| Shape | Count |
|---|---|
| `N/N` | 6914 |
| `N/N (c. N)` | 351 |
| `N/N (c.N)` | 269 |
| `N` | 205 |
| `N/N (w.N)` | 154 |
| `N (c. N)` | 112 |
| `N/N (w. N)` | 102 |
| `N/N (w. N) (c. N)` | 62 |
| `N/N (w.N) (c.N)` | 44 |
| `subsection (N)` | 38 |
| `N (c.N)` | 35 |
| `N/N (w.N)(c.N)` | 18 |
| `N/N(c.N)` | 18 |
| `(N)` | 17 |
| `sub-paragraph (N)` | 12 |
| `(c.N)` | 12 |
| `paragraph (N)` | 10 |
| `N.c.N` | 9 |
| `paragraph (a)` | 8 |
| `N. c.N` | 6 |
| `N. c. N` | 6 |
| `paragraph N` | 6 |
| `(b)` | 6 |
| `(c. N)` | 5 |
| `paragraph (b)` | 5 |
| `c.N` | 5 |
| `N/N (cN)` | 4 |
| `section Na` | 4 |
| `(a)` | 4 |
| `subsection (Na)` | 3 |
| `that schedule` | 3 |
| `c. N` | 3 |
| `tcta N` | 3 |
| `N/N (s. N)` | 2 |
| `s.i, N/N` | 2 |
| `N/N (w.N) (c. N)` | 2 |
| `N (w. N)` | 2 |
| `N/N (cy.N)(c.N) / (w.N)(c.N)` | 2 |
| `o.s. N/N` | 2 |
| `s.N.N/N (c.N)` | 2 |

## Examples: misroute

| Citation | Query (source text) | Target |
|---|---|---|
| `Income Tax Act 2007(c. 3)` | The new definition of charity has already been applied for the purposes of Chapter 2 of Part 8 of the Income Tax Act 2007(c. 3) (gift aid) (see paragraph 34 of Schedule 6 to the Finance Act 2010) | `uk/uksi/2007/3` |
| `182` | S.I. 2007/3538, 2008/1941, 2010/1159, 2849, 2011/226, 988, 1043, 2012/3082, 2013/755, 182, 1857, 2016/241,696, 738, 1146, 1154, 2018/721, 2019/188, 2020/904, 1540. | `uk/uksi/2012/182` |
| `S.I. 2005/2414` | S.I. 2005/2414. | `uk/uksi/2005/2529` |
| `S.I 2000/3199` | S.I. 1995/1541, S.I 1998/2226, S.I 2000/3199 and S.I 2006/958. | `uk/uksi/2003/3199` |
| `1438` | relevant amending instruments S.I. 1988/660, 999, 1438 and 1970, 1990/127 and 574, 1991/387, 1175 and 1520, 1992/573, 1101 and 2155, 1993/315, 963, 1249 and 2119 and | `uk/uksi/1988/1483` |
| `1431` | S.I. 1991/682, 1992/654, 1993/1062 and 1518, 1995/150, 554, 1085 and 3099, 1996/505 and 1431, 1997/651, 1998/538, 1001 and 3234, 2000/207 and 2211, 2002/1686 and 2021, 2003/714 and 2119, 2005/1805, 2006/1735, | `uk/uksi/1995/1431` |
| `The Nursing and Midwifery Order 2001 (S.` | The Nursing and Midwifery Order 2001 (S.I. 2002/253), arts. 1(2)(3), 54, Sch. 5 para. 5 (with savings in art. 3(18)) | `uk/uksi/2001/253` |

## Examples: dropped

| Citation | Query (source text) | Target |
|---|---|---|
| `3005 (W. 297)` | S.I. 2008/1430, 2009/2983 (W. 260), 2010/630 (C. 42)/ and 2013/2902 (W. 281) and 3005 (W. 297). | `uk/wsi/2013/3005` |
| `2004 (c.31)` | 1973 (c.32), 1977 (c.49), 1978 (c.29), 1985 (c.51), 1988 (c.49), 1994 (c.39), 1995 (c.17), 1997 (c.46), 1999 (c.8), 2001 (c.15), 2002 (c.17), 2003 (c.43), 2004 (c.31), 2006 (c.43), S.I. 1996/1008, S.I. 2002/2202, S.I. 20 | `uk/ukpga/2004/31` |
| `2023/217` | S.I. 2020/1462, 2021//211, 2022/735 and 2023/217. | `uk/uksi/2023/217` |
| `2022/360` | S.I. 2020/1400), 2021/1266, 2022/360, 1279. | `uk/uksi/2022/360` |
| `252` | 1039, 1070, 1076, 1094, 1129, 1161, 1190, 1227, 1238, 1277, 1292, 1323, 1337, 1360, 1424, 1517, 1595, 2021/18, 25, 38, 47, 49, 68, 98, 137, 150, 166, 223, 252, 348, 942, 1375 and 1644 and S.I. 2021/150. | `uk/uksi/2021/252` |
| `2586` | 2322, 2004/665 and 696, 2005/661 and 3074, 2006/600 and 2919, 2007/2054 and 3280, 2008/654 and 2263, 2009/381, 1298 and 2466, 2010/492 and 1634, 2011/591 and 2586, 2012/610, 2013/413, 2014/78, 570, 1607 and 3061 and as m | `uk/uksi/2011/2586` |
| `1331` | 1122 and 1331, and S.I. 2023/149, 440 and 665. | `uk/uksi/2022/1331` |
| `1991/1342` | in Part F in the entry for the Fishing Vessels (Safety Provisions) Rules 1975 there shall be added in column 3: “1991/1342” | `uk/uksi/1991/1342` |
| `1996/704` | relevant amending instruments are S.I.1993/2209 1995/3092, 1996/704, 1998/1648, 2000/3118 (W.226) and 2001/2706 (W.226). | `uk/uksi/1996/704` |
| `2446` | S.I. 1998/666 and 2216, 2000/605, 2002/561 and 2469, 2003/631 and 2322, 2004/665, 2005/661 and 3074, 2006/600 and 2919, 2007/3280, 2008/654 and 2263, 2009/381 2446, 2010/492 and 1634, 2011/2586 and 2012/610. | `uk/uksi/2009/2446` |
| `2013/606` | relevant amending instruments are S.I. 2009/274, 1975, 2010/43, 44, 747, 2011/651, 2012/1363, 2013/606, 2067, 2014/514, 2128, 2015/1510, 2017/723, 2018/1053, 2019/925, 2020/61, 416. | `uk/uksi/2013/606` |
| `731` | S.I. 1961/1441, 1966/1523. 1972/1339, 1537, 1973/242, 731, 1649. | `uk/uksi/1973/731` |
| `2022/735` | S.I. 2020/1462, 2021//211, 2022/735 and 2023/217. | `uk/uksi/2022/735` |
| `2013/413` | and 696, 2005/661 and 3074, 2006/600 and 2919, 2007/2054 and 3280, 2008/654 and 2263, 2009/381, 1298 and 2466, 2010/492 and 1634, 2011/591 and 2586, 2012/610, 2013/413, 2014/78 and 570 and as modified by S.I. 1996/971. | `uk/uksi/2013/413` |
| `2023/301` | S.I. 2022/991), 2023/301, 2023/576 and 2024/281. | `uk/uksi/2023/301` |

## Examples: wrong_provision

| Citation | Query (source text) | Target |
|---|---|---|
| `Part 2` | An offence under Part 2 of the Serious Crime Act 2007 in relation to a relevant offence. | `uk/ukpga/2007/27/pt2` |
| `Chapter A3` | an integrated care board established under Chapter A3 of Part 2 of the National Health Service Act 2006, | `uk/ukpga/2006/41/pt2/chA3` |
| `Part 4` | Treatment of exchange gains and losses under Part 4 of TIOPA 2010 | `uk/ukpga/2010/8/pt4` |
| `Chapter A3` | an integrated care board established under Chapter A3 of Part 2 of the National Health Service Act 2006, | `uk/ukpga/2006/41/pt2/chA3` |
| `Part VII` | remuneration on suspension on medical grounds, or on maternity grounds, under Part VII of the Employment Rights Act 1996 (suspension from work) | `uk/ukpga/1996/18/ptVII` |

## Examples: false_abstention

| Citation | Query (source text) | Target |
|---|---|---|
| `S.I. 1996/1919 (N.I. 16)` | S.I. 1996/1919 (N.I. 16), art. 257, Sch. 3 (with Sch. 2) | `uk/nisi/1996/1919` |
| `1988 (c. 40)` | the Education Reform Act 1988 (c. 40), Schedule 12, paragraph 91, by the Further and Higher Education Act 1992 (c. 13), Schedule 8, paragraph 19, and by the | `uk/ukpga/1988/40` |
| `1998 c. 11` | 1998 c. 11, s. 29(2) | `uk/ukpga/1998/11` |
| `Finance Act 2000 (c. 17)` | Finance Act 2000 (c. 17), s. 112(4) | `uk/ukpga/2000/17` |
| `Finance (No. 2) Act 2023 (c. 30)` | Finance (No. 2) Act 2023 (c. 30), Sch. 2 paras. 8(4)(b), 14(2)(b) | `uk/ukpga/2023/30` |
| `2020 c. 1` | Reg. 47 in force at 31.12.2020 on IP completion day (in accordance with 2020 c. 1, Sch. 5 para. 1(1)), see reg. 1 | `uk/ukpga/2020/1` |
| `S.I. 2019/1212` | S.I. 2019/1212, regs. 1(3), 22(3)) and The Financial Services (Miscellaneous) (Amendment) (EU Exit) Regulations 2019 (S.I. 2019/710), | `uk/uksi/2019/1212` |
| `Merchant Shipping Act 1979 (c. 39)` | article 4 of the Hovercraft (Application of Enactments) Order 1989 (S.I. 1989/1350) (sections 85and 86 re-enact sections 21 and 22 of the Merchant Shipping Act 1979 (c. 39) which are referred to in that article) | `uk/ukpga/1979/39` |
| `S.I. 2010/976` | article 12 of, paragraphs 47 and 71 of Schedule 14 to, S.I. 2010/976, section 74 of, paragraphs 121 and 139 in Part 6 of Schedule 8 to, the Serious Crime Act 2007 (c.27), and section 15 | `uk/uksi/2010/976` |
| `2020 c. 1` | Sch. 4 para. 15 in force at 31.12.2020 on IP completion day (in accordance with 2020 c. 1, Sch. 5 para. 1(1)), see reg. 1(3) | `uk/ukpga/2020/1` |
| `Legislative and Regulatory Reform Act 20` | the Legislative and Regulatory Reform Act 2006 (c. 51), section 27(1)(a) and the European Union (Amendment) Act 2008 (c.7), Schedule 1, paragraph 1. | `uk/ukpga/2006/51` |
| `1999 (c. 8)` | the Health Act 1999 (c. 8) (“the 1999 Act”), section 2(1) | `uk/ukpga/1999/8` |
| `The Social Security Benefits Up-rating O` | The Social Security Benefits Up-rating Order 2015 (S.I. 2015/457), arts. 1(2)(f), 15 | `uk/uksi/2015/457` |
| `S.I. 1991/828` | S. 43 wholly in force at 14.10.1991 see s. 108(2)(3) and S.I. 1991/828, art. 3(2) | `uk/uksi/1991/828` |
| `S.I. 1997/2668` | S.I. 1997/2668, art. 2, Sch | `uk/uksi/1997/2668` |

## Examples: miss

| Citation | Query (source text) | Target |
|---|---|---|
| `2005/1444` | 2005/1444 | `uk/uksi/2005/1444` |
| `2012/57` | 2012/57 | `uk/uksi/2012/57` |
| `2005/1521` | 2005/1521 | `uk/uksi/2005/1521` |
| `2008/1476` | 2008/1476 | `uk/uksi/2008/1476` |
| `2004/3203 (C.139)` | 2004/3203 (C.139) | `uk/uksi/2004/3203` |
| `2008/1316` | 2008/1316 | `uk/uksi/2008/1316` |
| `1999 (c.14)` | 1999 (c.14) | `uk/ukpga/1999/14` |
| `1996/505` | Nos. 1991/146, 1991/682, 1991/1179, 1992/654, 1993/1062, 1993/1518, 1995/150, 1995/554, 1995/1085, 1995/3099, 1996/505 and 1996/1431. | `uk/uksi/1996/505` |
| `2018/652` | 2018/652 | `uk/uksi/2018/652` |
| `2007/3285 (W.289)` | 2007/3285 (W.289) | `uk/wsi/2007/3285` |
| `1985 (c. 66)` | 1985 (c. 66) | `uk/ukpga/1985/66` |
| `2005/275` | 2005/275 | `uk/uksi/2005/275` |
| `1987/2158` | 1987/2158 | `uk/uksi/1987/2158` |
| `2012/1205` | 2012/1205 | `uk/uksi/2012/1205` |
| `2008/3168 (C. 143)` | 2008/3168 (C. 143) | `uk/uksi/2008/3168` |

## Examples: ambiguous

| Citation | Query (source text) | Target |
|---|---|---|
| `S.I. 2014/954` | S.I. 2014/954, art. 2(e) (with art. 3) (with transitional provisions and savings in S.I. 2014/956, arts. 3-11) | `uk/uksi/2014/954` |
| `1986 (c.45)` | in other respects the process is the same as for normal administration under the Insolvency Act 1986 (c.45), subject to modifications specified in Schedule 10 to the 2011 Act. | `uk/ukpga/1986/45` |
| `1990 (c. 16)` | Regulation 6 is made under section 16 of the Food Safety Act 1990 (c. 16) to amend the Honey (Wales) Regulations 2015 to set the method of analysis that food authorities must use to verify | `uk/ukpga/1990/16` |
| `S.I. 2014/956` | S.I. 2014/954, art. 2(e) (with art. 3) (with transitional provisions and savings in S.I. 2014/956, arts. 3-11) | `uk/uksi/2014/956` |
| `1981 (c. 56)` | the Transport Act 1981 (c. 56) sections 18 and 40 and Schedule 6, paragraph 5(3) and Schedule 12 (Part II) and by the Marine and Coastal Access Act | `uk/ukpga/1981/56` |
| `S.I. 1987/460 (N.I. 5)` | S.I. 1987/460 (N.I. 5), art. 4A (as inserted (31.3.1995) by 1993 c. 8, s. 25, Sch. 4 Pt | `uk/nisi/1987/460` |
| `2015 (c. 26)` | Part 8 provides for review of the operation of the Regulations for the purpose of the Small Business, Enterprise and Employment Act 2015 (c. 26). | `uk/ukpga/2015/26` |
| `1977 (c. 52)` | Police Negotiating Board Act 1980 (c. 10), paragraph 28 of Schedule 7 to the Police Act 1996 (c. 16) and section 1(1) of the Police and Firemen’s Pensions Act 1977 (c. 52) | `uk/ukpga/1977/52` |
| `1989 (c.42)` | section 158 of the Local Government and Housing Act 1989 (c.42) and by section 15(1) of, and paragraphs 82 and 85(1) of Part 1 of Schedule 4 to, the Constitutional Reform Act 2005 | `uk/ukpga/1989/42` |
| `1997 (c. 46)` | (Wales) (Consequential Amendments) (No. 2) Order 1996 (S.I. 1996/1008), the Schedule, paragraph 1, and the National Health Service (Primary Care) Act 1997 (c. 46), Schedule 2, paragraph 1(4). | `uk/ukpga/1997/46` |
| `The Value Added Tax (Reduced Rate) Order` | The Value Added Tax (Reduced Rate) Order 2002 (S.I. 2002/1100), art. 4(b) | `uk/uksi/2002/1100` |
| `1989 (c. 26)` | sections 45(3) and 187(1) of, and Part IV of Schedule 17 to, the Finance Act 1989 (c. 26), and extended by section 98A of the Taxes Management Act 1970 (c. 9) as inserted by section 165(1) of the Finance Act | `uk/ukpga/1989/26` |
| `S.I. 2015/33` | S.I. 2015/33, art. 4 (with art. 6) (as amended: (11.2.2015) by S.I. 2015/101 | `uk/uksi/2015/33` |
| `section 2` | section 2 (destroying, damaging or endangering safety of aircraft) | `uk/ukpga/1982/36/s2` |
| `paragraph 14` | In Schedule 1 (pupil referral units), for paragraph 14 substitute— | `uk/ukpga/1996/56/sch1/para14` |

## Reading this report (hand-written, 28 Sept 2026)

Generated by `uv run python -m eval.sweep run --harvest data/harvest/uk_citations.jsonl --index data/index --sample 100000 --out reports/coverage-sweep-uk.md` over the full Stage B index: 134,219 instruments (the 421 re-fetched pre-1963 Acts included), 5.7M coordinates, and the full catalogue of 244,564 instruments. The sample is drawn with the fixed seed from the 1,379,044 eligible `sweep` citations. The re-fetch added citations to the harvest, so this sample is a different draw from the previous report's. Every query is the clause of the source text that holds the citation (`eval.sweep.replay_query`), so each row is a citation written by a drafter, not by us.

What the buckets hold, from inspecting them:

- **misroute (7):** all are errors in the source's own link target: the text is read correctly and the `<Citation>` URI is wrong. Examples: "Income Tax Act 2007 (c. 3)" linked to SI 2007/3; "The Nursing and Midwifery Order 2001 (S.I. 2002/253)" linked to 2001/253; "S.I. 2005/2414" linked to 2005/2529; list items linked to the wrong year ("1996/505 and 1431" linked to 1995/1431).
- **dropped (107):** list items the router never recognised while binding the rest of the clause, and provisions it saw but left unlinked. The list items are source typos ("S.1.2006/3434", "2021//211"), replay windows that cut off the "S.I." cue, or list items after an outer closing bracket ("(… S.I. 2022/991), 2023/301"). The unlinked provisions are a host provision followed by an annotation, as in "section 33(3A) (inserted by section 18 of the … Act 2024)". There the router binds the amending Act's s. 18 and correctly declines to guess which Act s. 33 belongs to.
- **miss (8,541):** about 7,900 are bare `yyyy/n` cells from commencement tables, with or without a series note ("2008/3244 (C. 148)") and with no "S.I." cue. That is a documented unsupported form (grammar.md UK-U-05). Most of the rest are the same tables' cells holding a number alone ("963", "963 (C. 41)") under a year row, and relative references ("subsection (2)", "that section", UK-U-02).
- **false_abstention (6,333):** mostly provisions the current text no longer has (repealed articles whose text is dots, subsections removed by amendment). By decision 19 these get a plain refusal. Also savings provisions cited in "(with …)", and host provisions linked across annotation prose.
- **ambiguous (4,371):** the intended questions: `provision_without_instrument` 2,571, `title_number_conflict` 694, `context_needed` 428, `year_only` 303, and smaller groups. The 21 `number_mismatch` questions are cases where a title and its bracketed SI number name different SIs. Most are drafting typos in the source: "Waste (England and Wales) Regulations 2011 (S.I. 2011/998)" is really 2011/988.

Stage A (partial data, 20,000 citations) is kept in `coverage-sweep-uk-stageA.md` for comparison. Its sample held few SIs, because few were downloaded then.
