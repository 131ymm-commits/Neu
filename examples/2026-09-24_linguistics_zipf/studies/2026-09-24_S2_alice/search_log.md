# Журнал поиска S2 (агенты, 24.09.2026)

Сырые отчёты четырёх агентов поиска источников. Числа подсчёта слов из отчёта критика сюда НЕ переносятся: см. ERRORS № 14.

## Группа ger
- **English (original)** — n/a (Lewis Carroll original), 1865. Доступ: `200 173595`. Published 1865; the author died in 1898. Project Gutenberg release #11.
- **German** — Antonie Zimmermann, 1869 (Leipzig, Johann Friedrich Hartknoch; PG release 2007). Доступ: `200 183285`. Translation published in 1869 and distributed by Project Gutenberg as public domain (#19778); the translator was a 19th-century figure, so the term has long expired.
- **Dutch** — Alfred Kossmann (identified by matching chapter titles such as 'Een verkiezings-wedstrijd en een treurig verhaal' and 'Soepschildpad' against the DBNL Kossmann edition and bilinguis.com), 1947 (Kossmann/Reedijk). Доступ: `gist raw URL https://gist.githubusercontent.com/TranquilMarmot/471ef4eeb38447db5`. NOT public domain: Kossmann died in 1998, so the text is protected in the EU/NL until 2069. No source or licence is stated in the gist.
- **Swedish** — Nino Runeberg / Emily Nonnen / Louise Arosenius, 1921 / 1870 / 1898. Доступ: `not tested (no GitHub/PyPI copy found; sv.wikisource.org, litteraturbanken.se an`. Nonnen died 1905 and Runeberg died 1934, so both are public domain. Arosenius's dates were not checked.
- **Danish** — 'D. G.' (anonymous), 1875. Доступ: `not tested (only known digital copy is at runeberg.org/marievidun/, which is blo`. Anonymous work published in 1875; public domain on any term.
- **Norwegian** — Margrethe Horn (1903); E. A. Hagerup, i.e. Augusta and Emma Hagerup (1870 serial), 1903 / 1870. Доступ: `not tested (HathiTrust catalog record 100527150 and nb.no are blocked; no GitHub`. The 1870 serial and the 1903 book are likely public domain. Margrethe Horn's death year was not verified.
- **Icelandic** — Unknown (1937); revised in 1954 by Halldór G. Ólafsson, 1937. Доступ: `not tested`. Uncertain: the 1937 translation is anonymous (publication plus 70 years would give public domain in 2008), but the 1954 revision is probably still protected.
- **West Frisian** — Tiny Mulder (1921-2010), 1964 (reissued 1994 by Afûk; now published by Evertype). Доступ: `not tested`. NOT public domain: this is the first and only Frisian translation, and the translator died in 2010, so it is protected until 2081.

Тупики:
- GITenberg German repo-name guesses 'Alices-Abenteuer-im-Wunderland_19778' and 'Alice-s-Abenteur-im-Wunderland_19778': 404. In the correct repo 'Alice-s-Abenteuer-im-Wunderland_19778', 19778.txt and 19778-0.txt return 404 and only 19778-8.txt and README.rst are 200.
- api.github.com returns 403 (search) and 400 (contents); github.com web pages return 403/400; codeload.github.com zip returns 403; gist.githubusercontent.com returns 000. `git ls-remote` and `git clone` over https://github.com/... and https://gist.github.com/... DO work through the proxy.
- Project Gutenberg has no Alice translation in Swedish, Danish, Dutch, Norwegian, Icelandic or Frisian; repeated catalog searches found only de #19778, fr #55456, it #28371, fi and eo. GITenberg (a PG mirror) therefore cannot have them either.
- runeberg.org (Danish 1875 'Maries Hændelser' at /marievidun/; Swedish Nonnen 1870) is blocked for both curl and WebFetch (EGRESS_BLOCKED).
- sv.wikisource.org (Nino Runeberg 1921, complete in 12 chapters), litteraturbanken.se, dbnl.org, nb.no, babel.hathitrust.org, dp.la, web.archive.org and ws-export.wmcloud.org: all blocked (000).
- farkastranslations.com (000), bilinguis.com (403), evertype.com (000), kaggle.com (000), zenodo.org (000), object.pouta.csc.fi (OPUS-Books moses/xml zips, 000), huggingface.co / datasets-server (000), cdn.jsdelivr.net/gh (000): all blocked.
- Gist andersem/1462444 'alice.txt' is only a 1,326-byte English excerpt.
- mdahllof/lbpf (Swedish Litteraturbanken prose fiction corpus, cloned) contains no Carroll or Alice text.
- iglika88/corpus_original_adapted_literary_works: the corpus is not public (copyright); it has only metadata and tools.
- kb-dk/public-adl-text-sources (Danish ADL TEI texts) holds Danish authors only, no Carroll translation.
- lokal-profil/runeberg is only a downloader library and needs runeberg.org, which is blocked.
- GitLab API search (gitlab.com is reachable) for underlandet, eventyrland, vidunderlandet, sagolandet, undralandi and alice-multilingual: no results.
- PyPI search page returns a ~3 KB JS challenge (no results), and no PyPI package bundling Nordic or Dutch Alice texts was found via WebSearch.
- WebSearch site:github.com queries for 'sagolandet', 'Vidunderlandet', 'Eventyrland', 'Alices äventyr i underlandet', 'Maries Hændelser', 'Else i Eventyrland' and "Lize's avonturen" found no GitHub copies.
- The Dutch text found on GitHub is Kossmann's 1947 translation (copyrighted). The public-domain Dutch translations (1875 anonymous 'Lize', 1899 R. ten Raa) have no digital text found.
- Frisian: the only translation is Tiny Mulder's 1964 version (translator died 2010), so no public-domain text exists.

## Группа rom
- **French** — Henri Bué, 1869. Доступ: `200 184669`. Published 1869 (Macmillan, London). Bué died in 1929, so the translation is public domain in the US and in countries with life+70 terms.
- **Italian** — Teodorico Pietrocòla-Rossetti, 1872. Доступ: `200 173440`. Published 1872 (Macmillan, London). The translator died in 1883, so it is public domain everywhere.
- **Esperanto** — E. L. (Elfric Leofwin) Kearney, 1910. Доступ: `200 186987`. Published 1910. Kearney lived 1856-1913, so it is public domain everywhere.
- **German (extra, not in the requested list)** — Antonie Zimmermann, 1869. Доступ: `200 183285`. Published 1869 (Leipzig), more than 150 years ago. PG publishes it as public domain.
- **Finnish (extra, not in the requested list)** — Anni Swan, 1906 (first Finnish edition). Доступ: `200 166031`. PD in the US, where PG published it. Swan died in 1958, so under life+70 it is not public domain in Finland/EU until 1 January 2029.
- **English (baseline for comparison)** — (original), 1865. Доступ: `200 173595`. Published 1865. Carroll died in 1898.
- **Spanish** — Juan Gutiérrez Gili, 1927. Доступ: `not tested`. Gutiérrez Gili lived 1894-1939, so the translation is PD in Spain since 2020 (80 years after death). In the US, a 1927 publication has been PD since 2023. This is the only public-domain full Spanish t
- **Portuguese** — Monteiro Lobato, 1931. Доступ: `not tested`. Lobato died in 1948, so it is PD in Brazil and Portugal (life+70) since 2019. It is NOT yet PD in the US: a 1931 publication enters the US public domain on 1 January 2027.
- **Catalan** — Josep Carner, 1927. Доступ: `not tested`. Not PD in Spain or the EU: Carner died in 1970, so it stays in copyright until 2051. In the US, a 1927 publication has been PD since 2023.
- **Romanian** — Frida Papadache (first Romanian translation), 1945. Доступ: `not tested`. None; it is in copyright. The first Romanian translation dates from 1945, and all 20+ later ones are newer, including Claudia Stoian (Evertype, 2015).
- **Latin** — Clive Harcourt Carruthers, 1964. Доступ: `not tested`. None; it is in copyright. It was published in 1964 and Carruthers died in 1972. Evertype reissued it in 2011.
- **Ido** — Gonçalo Neves, 2020. Доступ: `not tested`. None; it is in copyright (Evertype, 2020).

Тупики:
- Sandbox reachability: raw.githubusercontent.com works, and so do `git ls-remote` and `git clone --depth 1 --filter=blob:none --no-checkout` against github.com. These are blocked with 403: api.github.com, github.com HTML pages, codeload/archive zips and the github.com/search page. gitlab.com (includi
- The server-side WebFetch tool is ALSO blocked for gutenberg.org, en.wikipedia.org, es.wikisource.org and cvc.cervantes.es. It DOES work for github.com, and GitHub repository search pages (github.com/search?q=...&type=repositories) render through it.
- Task input error: Esperanto PG #17961 is wrong; the Kearney Esperanto Alice is PG #17482. The GITenberg repo La-Aventuroj-de-Alicio-en-Mirlando_17961 does not exist; ..._17482 does.
- GITenberg repo names turned out to be guessable, and git accepts them case-insensitively: <Title-with-hyphens>_<PGid>. Confirmed: Aventures-d-Alice-au-pays-des-merveilles_55456, Le-avventure-d-Alice-nel-paese-delle-meraviglie_28371, La-Aventuroj-de-Alicio-en-Mirlando_17482, Alice-s-Abenteuer-im-Wund
- Project Gutenberg's Alice translations, per a WebSearch restricted to gutenberg.org, cover only French 55456, German 19778, Italian 28371, Esperanto 17482 and Finnish 46569. There are no Spanish, Portuguese, Catalan, Romanian, Latin or Ido editions, so GITenberg cannot supply those languages.
- GitHub repo searches through WebFetch turned up no usable text. 'alicia pais maravillas', 'alicia carroll' and 'alice no pais das maravilhas' found only web, CSS or game projects and 'PDF download' spam repos. 'terra meravelles', 'alicia terra mirabili', 'alicia marvelia', 'alice wonderland multilin
- Darrlop/AliciaHistogram alice_full_text.txt (raw 200 150507) is the ENGLISH PG text despite the Spanish repo name.
- literarybraids/literarybraids.github.io has only a 1.8 KB blog excerpt of Spanish Alice, not the full text. literarybraids/alice-spanish does not exist.
- iglika88/corpus_original_adapted_literary_works has only English Alice (TEI XML).
- RAYsSA-Chaves/Projeto_Alice (paginas.json and PDF) and guilhermegdadiniz/Livros-Eunice-Carneiro ('ALICE NO PAIS DAS MARAVILHAS.pdf', 1.8 MB, 256 pages) both contain André Cristi's modern Portuguese translation, a bilingual edition that is copyrighted. brunomr-bsb/RAG_Alice_Maravilhas contains only a
- OPUS Books / Farkas Translations: the Farkas site aligns Alice in en/hu/es/it/pt/fr/de/eo, but the Spanish and Portuguese translators are not identified and bulk redistribution is restricted. Hugging Face and OPUS are blocked, and the GitHub 'opus_books' repos I checked (npghuy/opus_books, piatpi/TR
- Grepping the PyPI simple index for alice/wonderland/alicia/carroll/gutenberg/wikisource/bilingual and running an npm registry search found no package that ships a multilingual Alice text.
- A GitLab project search for alicia, alice-in-wonderland, gutenberg and wikisource found nothing relevant. GitLab blob (code) search needs authentication (401).
- Portuguese: Lobato's 1931 adaptation is complete on pt.wikisource and archive.org, both blocked from the sandbox, and I found no GitHub mirror.
- Spanish: the only public-domain full translation is Gutiérrez Gili's 1927 text, and I found no digital copy on any reachable host.

## Группа sla
- **Bulgarian** — Lazar Goldman (Лазар Голдман), 1933 (first Bulgarian translation, Sofia, T. F. Chipev); this digital text is from the 4th edition, Pan, Sofia 1996. Доступ: `200 233973`. Not confirmed. The translation dates from 1933. Goldman was born about 1909, and his fate after the 1930s is unknown (litvestnik.com, 2021). Bulgaria protects works for 70 years after the author's dea
- **Czech** — Aloys Skoumal and Hana Skoumalová, 1961 translation; text follows the Albatros edition of 1983; MKP electronic edition 2021/2022. Доступ: `200 10331 (chapter 1 only). All 12 Wonderland chapter files returned 200, 134350`. NOT public domain. Aloys Skoumal died in 1988, and the library's colophon says the text is under copyright. It is free to read and download from the Prague Municipal Library's official web-book repo, 
- **English (baseline, not requested)** — n/a (original), 1865. Доступ: `200 167546`. Published in 1865; the author died in 1898.
- **Russian** — (anonymous) «Соня в царстве дива» 1879; P. S. Solovyova (Allegro) 1909; also A. N. Rozhdestvenskaya and A. D'Aktil on ru.wikisource, 1879 / 1909. Доступ: `not tested`. 1879 anonymous work; Solovyova died in 1924; D'Aktil died in 1942. All of these are public domain in Russia. None is reachable from this sandbox.
- **Polish** — Adela S. «Przygody Alinki w Krainie Cudów» 1910 (public domain); Jarek Westermark «Alicja w Krainie Czarów» 2026 (Free Art License 1.3, not public domain), 1910 / 2026. Доступ: `not tested`. The 1910 translation is effectively anonymous. Under Polish law an anonymous work is protected for 70 years from publication, so it has been public domain since 1981.
- **Ukrainian** — Halyna Bushyna (first complete Ukrainian translation), 1960. Доступ: `not tested`. None. The earliest translation (1960) is still under copyright.
- **Serbian** — unknown (first Serbian translation not identified), unknown. Доступ: `not tested`. None identified.

Тупики:
- GITenberg: the official repo list (gitenberg-dev/gitberg, gitenberg/data/GITenberg_repo_list.tsv, 72553 lines, up to PG id ~72856) has Alice only in English (#11, #928, #19033, #28885 and others), Esperanto (#17482), German (#19778), Italian (#28371), Finnish (#46569) and French (#55456). There is n
- Network: gutenberg.org, wikisource (ru/pl/cs), archive.org, huggingface.co, chitanka.info, wolnelektury.pl, rusneb.ru, wbc.poznan.pl, Kramerius/NKP, ririro.com, lib.ru (403), az.lib.ru (403), zenodo, codeberg, gist.githubusercontent.com, jsdelivr and *.github.io are all blocked from the sandbox. Web
- Reachable: raw.githubusercontent.com, git over github.com (git ls-remote and blob-less clone), pypi.org JSON, the gitlab.com API (project search and repo tree), registry.npmjs.org search, rubygems and proxy.golang.org. api.github.com search and contents endpoints refuse requests because this session
- Warning for anyone repeating this: with a --filter=blob:none clone, 'git ls-tree -l' fetches every blob to get sizes. On chitanka/content-text it started downloading the whole repo. Use --name-only.
- d0rj/RusLit (390 files): no Carroll or Alice.
- ancatmara/DL-SFL-2019 (course on parallel corpora): no Alice texts.
- averkij/lingtrain-aligner: sample_texts contains only an Agatha Christie en/ru pair.
- nullspace05/ParallelTexts: a web app; aligned books are not in the repo.
- AleksandrKopylov/alice_in_wonderland: HTML/CSS only. boulingua/scriptlibrary: English Alice with alphabet-practice transliterations, not translations.
- lgnbhl/wikisourcer (R): a download client with no bundled texts. krzjoa/wolne_lektury (PyPI wolne-lektury 0.1.0): an API client only, and wolnelektury.pl is blocked.
- Guessed repo names that do not exist on GitHub: fnp/wl-texts, fnp/lektury, fnp/wolnelektury-texts, fnp/texts, fnp/wolnelektury-sources, fnp/sources, fnp/wl-sources, fnp/xml, fnp/wlxml, fnp/teksty, fnp/utwory; several books-are-next/carroll-alencina-* variants; averkij/lingtrain-books and similar; Gu
- books-are-next/library urls.yml lists only 2 books, so there is no catalogue of that org.
- GitLab project searches for alice/alisa/alicja/alenka/carroll/wikisource/chitanka/russian books/parallel corpus found nothing relevant. dremovd/original-translation-books holds only metadata CSVs.
- PyPI (898k package names grepped) and npm search: no package ships Slavic Alice texts.
- farkastranslations / OPUS Books has Alice only in en, hu, es, it, pt, fr, de, eo; there is no Slavic language.
- The EvLab 'Alice localizer' materials are short passages in many languages, not full books.
- WebSearch with site:github.com, github.io or filetype:txt for «Соня в царстве дива», «Аня в стране чудес», Allegro/Solovyova, «Przygody Alinki», «Alicja w Krainie Czarów», «Alisa u zemlji čuda», «Аліса в Країні Див» and «Алиса в страната на чудесата» found no GitHub-hosted copies. Only the Czech MKP

## Группа oth
- **Finnish** — Anni Swan (verses with Otto Manninen), 1906 (PG release 2014-08-12). Доступ: `200 166031`. Published in 1906, so PD in the USA (it is on Project Gutenberg). Swan died in 1958, so it only enters the public domain in Finland/EU on 2029-01-01.
- **Hebrew** — Aryeh Leib Semiatitzky (pen name L. Seman), 1883-1945, 1923/1924 (Omanut, Frankfurt a.M.). Доступ: `200 194198`. The translator died in 1945, so it is PD in Israel (life+70). It was published in 1924, so it is PD in the USA. It ships in Project Ben-Yehuda's official public-domain dump on GitHub.
- **Japanese** — Ōkubo Yū (大久保ゆう), 2015 (Aozora Bunko work 57320). Доступ: `200 249137`. NOT public domain. The file footer says it is released by the translator under CC BY 4.0, so free reuse with attribution. No PD Japanese translation is reachable: the 1927 Kikuchi Kan / Akutagawa 'アリス
- **German** — Antonie Zimmermann, 1869. Доступ: `200 183285`. Published in 1869 and the translator is long dead; PD everywhere.
- **French** — Henri Bué, 1869. Доступ: `200 184669`. Published in 1869; PD everywhere.
- **Italian** — Teodorico Pietrocòla-Rossetti, 1872. Доступ: `200 173440`. Published in 1872; PD everywhere.
- **Esperanto** — E. L. Kearney, 1910. Доступ: `200 186987`. Published in 1910; PD in the USA and in PG's jurisdiction.

Тупики:
- Sandbox egress: github.com HTML pages and the GitHub REST API (api.github.com) return 403 ('sessions are bound to their configured repositories'). raw.githubusercontent.com works, and so do `git ls-remote` and blobless `git clone --filter=blob:none --no-checkout` of public repos, which is how file t
- Finnish: GITenberg/Liisan-seikkailut-ihmemaailmassa_46569 does not exist, because the PG title is 'ihmemaassa'. In the correct repo, 46569.txt and 46569-0.txt return 404; only 46569-8.txt exists.
- GITenberg repo list gitenberg-dev/giten_site/master/assets/GITenberg_repos_list_2.tsv (200, 5.8 MB): it only covers PG IDs up to about 46441, so newer repos (46569, 55456) must be found by guessing the name and checking with git ls-remote.
- PG metadata (hugovk/gutenberg-metadata JSON, 68,502 books, mid-2022): the only non-English Carroll books on PG are 17482 eo, 19778 de, 28371 it, 46569 fi and 55456 fr. There is no PG Hungarian, Estonian, Turkish, Irish, Welsh, Hebrew, Chinese, Japanese, Tagalog or Hawaiian Alice.
- Hungarian: Kosztolányi's 'Alice Csodaországban' (1936; he died in 1936, so PD in Hungary since 2007, but probably still protected in the US under URAA until 2031) is only on MEK 00348 (blocked) and OSZK/Scribd PDFs. No GitHub or PyPI copy was found. Hunglish, NerKor and ELTeC-hun do not appear to in
- Chinese: Zhao Yuanren's 阿麗思漫遊奇境記 (1922; PD in the US by publication date, not in China/Taiwan until about 2033). The only GitHub hit, dpublishing/epub3guide practices/05_Wrap_Text_Around_Image, is a sample EPUB with a single ~14 KB chapter (p-001.xhtml), not the full book. The full text exists only 
- Japanese PD: the Kikuchi Kan / Akutagawa 'アリス物語' (1927; Aozora works 61044/61046) is absent from both aozorahack/aozorabunko_text (last updated 2023-03) and P4suta/aozorabunko_text (updated 2026-06). The official aozorabunko/aozorabunko repo returns 404 on raw and fails git ls-remote.
- Estonian: the first translation is Linda Bakis with Ants Oras, 1940 (Oras died in 1982), so it is not PD. Later translations are by Kross (1971), Tiisma (2015) and Klein/Märjamaa (2018). No digital text was found.
- Turkish: all known translations are from the 1930s or later with non-expired translator copyright (e.g. Kısmet Burian; modern ones by Ekici and Ezber). No PD digital text was found.
- Irish: Pádraig Ó Cadhla's 1922 translation (he died in 1948) is PD in the EU and US, but no online digital text exists; it is only a print reissue by Evertype. Nicholas Williams' 2003 translation is copyrighted.
- Welsh: the first translation is Selyf Roberts, 1953, which is copyrighted. No PD Welsh text exists.
- Hawaiian: R. Keao NeSmith's translation (Evertype, 2012) is copyrighted. No PD text exists.
- Tagalog: no PD or open-licensed translation located.
- PyPI: no package was found that ships translated Alice texts; results were translation tools such as py-translate. PyPI is not a viable source.
- Multilingual parallel corpora (OPUS Books / Farkas bilingual books) likely contain some Alice translations, but OPUS, Hugging Face and farkastranslations.com are all blocked and no GitHub copy was found.
