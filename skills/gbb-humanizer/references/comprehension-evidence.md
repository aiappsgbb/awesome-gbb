# Comprehension evidence behind the reader-first pass

Source notes for [`../SKILL.md` § GBB · Reader-first pass](../SKILL.md#gbb--reader-first-pass).
Sources were retrieved on 2026-10-23. Each row says how strong the support
is, so the skill does not present style advice as science.

Strength labels:

- **Experimental**: controlled studies or a corpus comparison with measured effects.
- **Standard**: official plain-language or style guidance. Authoritative for
  how institutions want text written, but not itself an experiment.
- **Practitioner**: widely cited advice with weak or secondary sourcing.

## Why removing AI tells is not enough

| Finding | Strength | Source |
|---|---|---|
| People who often use LLMs for writing detected AI-written articles with high accuracy. Their explanations cited "AI vocabulary" most, then formulaic sentence and document structure (for example optimistic, vague conclusions), originality and tone. Paraphrasing and prompting the model to avoid AI vocabulary did not remove all of these signals. | Experimental | Russell, Karpinska & Iyyer, *People who frequently use ChatGPT for writing tasks are accurate and robust detectors of AI-generated text*, ACL 2025. <https://arxiv.org/abs/2501.15654> |
| Instruction-tuned LLMs use present participial clauses at 2 to 5 times the human rate and nominalizations at 1.5 to 2 times, plus more `that` clauses as subjects and phrasal coordination: a noun-heavy, information-dense style. | Experimental (corpus) | Reinhart et al., *Do LLMs write like humans? Variation in grammatical and rhetorical styles*, PNAS 122(8), 2025. <https://doi.org/10.1073/pnas.2422455122> (preprint <https://arxiv.org/abs/2410.16107>) |

## How readers understand text

| Principle in the skill | Finding | Strength | Source |
|---|---|---|---|
| Lead with the point | 79% of test users scanned new web pages; 16% read word by word. Concise text scored 58% higher on measured usability, scannable 47%, objective (non-promotional) 27%, all three combined 124%. | Experimental (usability, 1997) | Nielsen & Morkes, NN/g. <https://www.nngroup.com/articles/how-users-read-on-the-web/>, <https://www.nngroup.com/articles/concise-scannable-and-objective-how-to-write-for-the-web/> |
| Lead with the point | "Lead with what's most important. Front-load keywords for scanning." | Standard | Microsoft Writing Style Guide, Top 10 tips. <https://learn.microsoft.com/style-guide/top-10-tips-style-voice> |
| Name who does what | Active voice makes clear who should do what; present tense is the simplest verb form. | Standard | Digital.gov, *Writing for understanding*. <https://digital.gov/guides/plain-language/writing> |
| Name who does what | Prefer active verbs and avoid nominalizations (Italian public services). | Standard | Designers Italia, *Linguaggio*. <https://designers.italia.it/design-system/fondamenti/linguaggio> |
| Given before new | Sentences that open with information the reader already has and end with new information are understood faster; violating the order slows comprehension. | Experimental | Haviland & Clark 1974; Clark & Haviland, *Comprehension and the given-new contract*, 1977. |
| Given before new | Topic and stress positions as a writing method. | Practitioner (argued, little direct testing) | Gopen & Swan, *The Science of Scientific Writing*, American Scientist 78, 1990. |
| Be concrete | Concreteness was the strongest predictor of comprehensibility, interest and recall across text types. | Experimental | Sadoski, Goetz & Fritz, *Journal of Educational Psychology* 85(2), 1993; Sadoski, Goetz & Rodriguez, *Journal of Educational Psychology* 92(1), 2000. <https://psycnet.apa.org/record/2000-03003-007> |
| Cut what the reader doesn't need | Coherence principle: people learn more deeply when extraneous material is excluded (23 of 23 tests, median effect size 0.86). Signaling the structure also helps (24 of 28 tests). | Experimental (multimedia learning) | Mayer & Fiorella, *Cambridge Handbook of Multimedia Learning*, ch. 12, 2014. |
| Plain words | Needlessly complex vocabulary lowered readers' judgements of the author's intelligence. | Experimental | Oppenheimer, *Applied Cognitive Psychology* 20, 2006. <https://doi.org/10.1002/acp.1178> |
| Plain words | Collected studies in which readers, including judges and lawyers, preferred and understood plain-language versions. | Practitioner (compilation of studies) | Kimble, *Writing for Dollars, Writing to Please*, 2nd ed., 2023. |
| Sentence length | Check sentences over 25 words and split them if you can. | Standard | GOV.UK A to Z style guide, *Sentence length*. <https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/style-guides/a-to-z-style-guide> |
| Sentence length | "14-word sentences: over 90% understood; 43 words: under 10%." | Practitioner (secondary source; indicative only) | Inside GOV.UK blog, 2014. <https://insidegovuk.blog.gov.uk/2014/08/04/sentence-length-why-25-words-is-our-limit> |
| Fit explicitness to the reader | Explicit links and definitions helped low-knowledge readers; high-knowledge readers sometimes learned more from less cohesive text. | Experimental | McNamara, Kintsch, Songer & Kintsch, *Cognition and Instruction* 14(1), 1996. |

## Limits

- Most comprehension studies use expository or instructional text, not sales
  copy. They support clarity rules; they do not measure whether a reader thinks
  a text "sounds AI".
- Readability formulas and word lists can flag problems. Meeting them does not
  show that readers understand the text.
- The local before/after generations used to check this skill are examples,
  not a reader study. They are recorded in the pull request that introduced
  this file.
