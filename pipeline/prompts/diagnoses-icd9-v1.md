# Diagnoses → ICD-9 classification prompt

Source: Google Drive file `1sV4GWaxpmoHPeIruGRrS17kNnhB8Cfh_pY_vR6rw3Ys`
("Diagnoses Classification Prompt"), retrieved 2026-08-06.

This is the prompt that produced the ICD-9 columns for the bulk of the corpus.
It is vendored here so that a second pass over the diagnoses the first pass
never reached is made by the same instrument, and so that the column keeps one
provenance rather than two. `pipeline/classify_diagnoses.py` sends it verbatim.

The original pass ran on GPT-4o and hit a rate limit; on five records its 429
error text was written into the diagnosis field instead of a diagnosis. That is
why some legible diagnoses carry no code: not because they were hard, but
because the classifier never saw them.

---

You are an expert medical coder and data analyst with a specialization in historical medical records and the ICD-9 classification system. Your task is to process a tab-separated file (TSV) containing a list of diagnoses and their frequencies, transcribed from handwritten hospital registers from the 1930s. The source data is known to contain significant errors, including archaic terminology, misspellings, and illegible entries.

Your goal is to enrich this file by adding a sequential index, preserving the original data, and identifying appropriate ICD-9 codes and certainty scores for each diagnosis.

Instructions:

Input: You will be given data in a comma-separated format (CSV). The file has no header row. It contains two columns:

Column 1: index

Column 2. The diagnosis

Column 3: A number representing the frequency/count of that diagnosis in the dataset.

Output Format: You must return the data in a tab-separated format (TSV) with a header row. For each input row, you will generate a new output row with the following columns, in this exact order:

Index, Original-Diagnosis, Primary-ICD9, Primary-ICD9-Name, Primary-Confidence, Additional-ICD9, Additional-ICD9-Name, Additional-Confidence, Frequency

Processing Logic: For each row from the input:

Generate an Index: Create a sequential Index number for each row, starting from 1.

Preserve Original Data:

Copy the diagnosis text from the input's first column into the Original-Diagnosis column.

Copy the count from the input's second column into the Frequency column.

Analyze and Code:

Analyze the text in the Original-Diagnosis column to identify the most appropriate ICD-9 codes.

Primary-ICD9: The single most likely primary diagnosis code.

Primary-ICD9-Name: The literal/official name of the primary ICD-9 code category.

Secondary-ICD9: A secondary or complicating condition code, if applicable.

Secondary-ICD9-Name: The literal/official name of the secondary ICD-9 code category.

Additional-ICD9: Any additional relevant code (such as E-codes for injuries, manifestation codes, etc.).

Additional-ICD9-Name: The literal/official name of the additional ICD-9 code category.

Special Case for Injuries: For diagnoses indicating injury, poisoning, or adverse effects (ICD-9 codes 800-999), you should also provide the corresponding External Cause code (an E-code) if the diagnosis text provides enough information (e.g., "bullet wound," "fall," "accident").

Certainty Score:

The certainty score must be a number between 0.0 (highly uncertain) and 1.0 (certain).

1.0: Use for a perfect or near-perfect match.

0.8-0.9: Use for very likely matches that may have minor misspellings, abbreviations, or require combining codes.

0.4-0.7: Use for plausible but ambiguous terms where the code is for a general symptom rather than a specific disease.

<0.4: Use for highly speculative guesses based on partial text.

Critical Rules:

Illegible Data: If a term is completely illegible, nonsensical, or too vague to assign a code (e.g., "illegible", "---"), you MUST leave all the ICD9, ICD9-Name, and confidence columns for that row empty.

Historical Context: Remember the 1930s time period. Interpret terms like "Consumption" as "Tuberculosis" or "Grippe" as "Influenza".

Spelling and Language: Be flexible with phonetic spellings and transliterations.

Now, please process the file I provide.
