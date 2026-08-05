# Gemini v1 extraction prompt — Hospital Registers

Source: Google Drive file `1EZreFPSmftJpg-7PYpdtkUlF4H4xOztFci3XCGg5NOA`
("Hospital Registers prompt"), retrieved 2026-06-18.

**Model:** Gemini 2.5 (in AI Studio — https://aistudio.google.com/)

**Output:** Tab-separated values, 32 columns (the consolidated dataset at
`data/public/hospital-registers-2025-08-10.tsv` has 53 columns; the extra 21
are added by downstream standardization/QA, not by this prompt).

---

Please transcribe the data from the image provided **[Identify the specific image here]**.

Format the output as **Tab-Separated Values (TSV)**.

Ensure the output includes exactly these columns, in this specific order:
index, age, age unit, sex, religion, nationality, occupation, address, city, next of kin and address, section or ward, standardized_ward, class, rate, gratis, Date of Admission, iso_admission_date, Date of Discharge, iso_discharge_date, No. of days in Hospital, calculated_days_stay, stay_discrepancy_flag, Diagnosis, standardized_diagnosis, Result, standardized_result, Serial No. of Bill, Remarks, source_reference, transcription_date_id, transcription_confidence, comments

**Processing Instructions:**

1. **Age Splitting:**
    - From the original 'Age' column (e.g., "30ys", "3ms"), extract the numerical value into the age column (e.g., 30, 3).
    - Extract the unit ('ys', 'ms', 'dy/ds', etc.) into the age unit column (e.g., ys, ms). If no unit is explicitly written, assume 'ys' and note this assumption in the comments column using the [assumed_age_unit] flag for that row.

2. **Religion/Nationality Splitting:**
    - From the original combined 'Religion and Nationality' column, split the entry into religion and nationality.

3. **Class/Rate Splitting:**
    - From the original 'Class and Rate' column, attempt to split the information into three columns: class ('1st', '2nd' or '3rd'), rate (numerical rate), and gratis. In the rate column, add the currency in round brackets if it is mentioned, e.g. (mils). In the gratis column write gratis if mentioned. If separation is unclear, place the best interpretation in class and leave rate blank, noting the ambiguity in comments with [class_rate_gratis_combined].

4. **Standardization:**
    - Provide standardized or expanded name for the Ward in the standardized_ward column (e.g. MAT->maternity, Surg->Surgical, B/S or BR ->British Section, Gen->Gynecology). If unsure, leave blank and use [uncertain_ward] in comments.
    - Provide the International Classification of Diseases ICD-9 code for Diagnosis in the standardized_diagnosis column. If unsure, leave blank and use [uncertain_diagnosis] in comments.
    - Provide standardized outcome terms for Result in the standardized_result column (e.g., "Recovered", "Improved", "Died", "Transferred", "Left Against Advice"). If unsure, leave blank and use [uncertain_result] in comments.

5. **Date Conversion (ISO 8601):**
    - Convert Date of Admission and Date of Discharge from DD.MM.YY format to YYYY-MM-DD format and place them in iso_admission_date and iso_discharge_date respectively. Assume the century is 19xx (e.g., '39' becomes '1939'). If a date is missing or illegible, leave the corresponding ISO column blank and note [missing_date] or [illegible_date] in comments.

6. **Location Extraction:**
    - Attempt to identify the primary city, town, or village name from the address or next of kin and address fields and place it in the city column. Be advised that these are addresses from Mandatory Palestine. If ambiguous locations are mentioned, note this in comments with [ambiguous_city].

7. **Stay Duration Calculation & Discrepancy:**
    - Calculate the stay duration by subtracting iso_admission_date from iso_discharge_date. Place this numerical value (number of days) in the calculated_days_stay column. (Note: This method typically excludes the discharge day).
    - Compare calculated_days_stay with the value transcribed in No. of days in Hospital. If they differ, or if the original number is non-numeric (like "One") and doesn't match the calculation, set stay_discrepancy_flag to FLAG. Otherwise, set it to OK. If calculation is impossible due to missing dates, leave stay_discrepancy_flag blank and note [duration_calc_impossible] in comments.

8. **Metadata & Confidence:**
    - Populate source_reference with the identifier for the source image **[e.g., 'image_register_3329-3339.jpg']**.
    - Populate transcription_date_id with the date of transcription and the model used (e.g., YYYY-MM-DD_Gemini_vX.Y).
    - Assign a transcription_confidence score per row (e.g., High, Medium, Low) based on the overall legibility and certainty of the transcription for that specific row.

9. **Comments and Flags:**
    - **Handling Transcription vs. Interpretation:**
        - In the Diagnosis column, prioritize transcribing the visible text as accurately as possible, preserving original spelling and form, even if unclear or non-standard.
        - Use the standardized_diagnosis column for the interpreted, corrected, or standard medical term.
        - Crucially: If the most plausible visual reading of a term strongly differs from the term you place in Diagnosis or standardized_diagnosis (because the visual reading is non-standard, illegible, or context suggests a different term was intended), you MUST note this in the comments column. Use the flag [visual_reading_divergence: 'literal reading'] where 'literal reading' is your best attempt at transcribing the actual ink marks. For example: [visual_reading_divergence: 'Blumic'].
    - Use the comments column to note any uncertainties, ambiguities, illegible text, assumptions made, or potential errors.
    - Use specific flags in square brackets [] within the comments where applicable, such as: [illegible], [uncertain_term], [possible_typo: actual_word], [calculation_error], [missing_data], [assumed_age_unit], [class_rate_combined], [ambiguous_city], [duration_calc_impossible], [date_format_issue].

10. **Formatting:**
    - Use a tab character (\t) as the delimiter between columns.
    - Include the exact header row specified above as the first line of the output.
    - Represent empty or missing information in the original document with empty fields (i.e., consecutive tabs) in the corresponding TSV columns, unless instructed otherwise (like for flags).

Please provide the full TSV output based strictly on these instructions.
