from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT

doc = SimpleDocTemplate(
    "NUS406_Intensive_Care_Theatre_Nursing_Study_Guide.pdf",
    pagesize=letter,
    rightMargin=0.7*inch, leftMargin=0.7*inch,
    topMargin=0.7*inch, bottomMargin=0.7*inch
)

styles = getSampleStyleSheet()

title_s = ParagraphStyle('T', parent=styles['Title'], fontSize=22, textColor=colors.HexColor('#0d2b45'), spaceAfter=4, alignment=TA_CENTER)
subtitle_s = ParagraphStyle('ST', parent=styles['Normal'], fontSize=11, textColor=colors.HexColor('#555'), alignment=TA_CENTER, spaceAfter=14)
h1_s = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=14, textColor=colors.white, backColor=colors.HexColor('#0d2b45'), spaceBefore=12, spaceAfter=5, leftIndent=-4, rightIndent=-4, borderPadding=(5,8,5,8))
h2_s = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#0d2b45'), spaceBefore=9, spaceAfter=3)
h3_s = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=11, textColor=colors.HexColor('#333'), spaceBefore=6, spaceAfter=2, fontName='Helvetica-Bold')
body_s = ParagraphStyle('B', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#333'), spaceAfter=3, leading=14)
bullet_s = ParagraphStyle('BL', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#333'), leftIndent=16, firstLineIndent=-10, spaceAfter=2, leading=14)
sub_s = ParagraphStyle('SB', parent=styles['Normal'], fontSize=9.5, textColor=colors.HexColor('#555'), leftIndent=30, firstLineIndent=-10, spaceAfter=2, leading=13)
hi_s = ParagraphStyle('HI', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#7b3f00'), backColor=colors.HexColor('#fff3cd'), leftIndent=8, rightIndent=8, borderPadding=5, spaceAfter=5, leading=14)
mn_s = ParagraphStyle('MN', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#1a4731'), backColor=colors.HexColor('#d4edda'), leftIndent=8, rightIndent=8, borderPadding=5, spaceAfter=5, leading=14)
mcq_s = ParagraphStyle('MQ', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#4a1942'), backColor=colors.HexColor('#f3e5f5'), leftIndent=8, rightIndent=8, borderPadding=5, spaceAfter=4, leading=14)
note_s = ParagraphStyle('NT', parent=styles['Normal'], fontSize=9.5, textColor=colors.HexColor('#0c3547'), backColor=colors.HexColor('#d1ecf1'), leftIndent=8, rightIndent=8, borderPadding=5, spaceAfter=4, leading=13)

NAVY = colors.HexColor('#0d2b45')
TEAL = colors.HexColor('#1a6b7a')
LIGHT = colors.HexColor('#f0f6fa')
ALTROW = colors.HexColor('#e8f4f8')

def b(t): return f"<b>{t}</b>"
def make_table(data, col_widths, header_color=NAVY):
    rows = []
    for i, row in enumerate(data):
        cells = []
        for j, cell in enumerate(row):
            fs = 9 if i > 0 else 9.5
            fn = 'Helvetica-Bold' if i == 0 else 'Helvetica'
            tc = colors.white if i == 0 else colors.HexColor('#222')
            ps = ParagraphStyle('tc', parent=styles['Normal'], fontSize=fs, fontName=fn, textColor=tc, leading=fs+3)
            cells.append(TableCell_p(cell, ps))
        rows.append(cells)
    t = Table(rows, colWidths=col_widths)
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), header_color),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, ALTROW]),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#aaa')),
        ('INNERGRID', (0,0), (-1,-1), 0.25, colors.HexColor('#ccc')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ])
    t.setStyle(style)
    return t

def TableCell_p(text, style):
    return Paragraph(str(text), style)

story = []

# COVER
story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("NUS406: INTENSIVE CARE &amp; THEATRE NURSING", title_s))
story.append(Paragraph("Complete Study Guide — Structural Questions &amp; MCQ Ready", subtitle_s))
story.append(HRFlowable(width="100%", thickness=2, color=NAVY))
story.append(Spacer(1, 0.05*inch))
story.append(Paragraph("Course Instructor: Prof. Eta Vivian Ayamba  |  Covers all lecture topics + 50+ MCQs with rationale", subtitle_s))
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ccc')))
story.append(Spacer(1, 0.1*inch))

# TABLE OF CONTENTS
story.append(Paragraph("  TABLE OF CONTENTS", h1_s))
toc = [
    "Section 1: Introduction to Critical Care Nursing (Definition & History)",
    "Section 2: The Intensive Care Nurse",
    "Section 3: The Critically Ill Client — Definition, Characteristics & Needs",
    "Section 4: The ICU — Environment, Features & Quality of Care",
    "Section 5: Common Problems of the Critically Ill Client",
    "  5a. Respiratory Problems",
    "  5b. Cardiovascular Problems (Shock & Arrhythmias)",
    "  5c. Neurological Problems (ALC, Delirium, ICP)",
    "  5d. Renal Problems (AKI & Electrolyte Imbalance)",
    "  5e. Gastrointestinal Problems (Malnutrition, Stress Ulcers, Constipation/Diarrhea)",
    "  5f. Infection Problems (Sepsis & HAIs)",
    "  5g. Skin, Mobility, Psychological & Communication Problems",
    "Section 6: Monitoring the Critically Ill Client",
    "Section 7: Nursing Care Plan of the Critically Ill Client",
    "Section 8: MCQ Tips & 50 Practice Questions with Answers",
]
for item in toc:
    story.append(Paragraph(item, bullet_s))

story.append(PageBreak())

# ============================================================
# SECTION 1: INTRO TO CRITICAL CARE NURSING
# ============================================================
story.append(Paragraph("  SECTION 1: INTRODUCTION TO CRITICAL CARE NURSING", h1_s))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Key Definitions"), h2_s))
story.append(Paragraph(f'<bullet>&bull;</bullet> {b("Critical Care")}: Specialized medical care for patients with life-threatening conditions requiring continuous monitoring, advanced interventions, and organ system support. Managed in ICU or HDU.', bullet_s))
story.append(Paragraph(f'<bullet>&bull;</bullet> {b("Critical Care Nursing")}: Specialized nursing focused on critically ill, unstable patients at high risk of life-threatening complications. Uses advanced technology, rapid decision-making, and multidisciplinary collaboration.', bullet_s))
story.append(Paragraph(f'<bullet>&bull;</bullet> {b("AACN Definition")}: "The specialty that deals specifically with human responses to life-threatening problems."', bullet_s))
story.append(Paragraph(f'<bullet>&bull;</bullet> {b("WHO Definition")}: Care that improves outcomes of patients with acute life-threatening illnesses through timely and effective interventions.', bullet_s))

story.append(Paragraph(b("Characteristics of Critical Care Nursing"), h2_s))
for item in ["Holistic and patient-centered care", "High level of technical skill", "Evidence-based practice", "Ethical decision-making", "Emotional support for patients and families"]:
    story.append(Paragraph(f'<bullet>&bull;</bullet> {item}', bullet_s))

story.append(Paragraph(b("Goals of Critical Care Nursing"), h2_s))
story.append(Paragraph("Preserve life | Restore health | Prevent complications | Provide comfort and support | Assist in end-of-life care when necessary", hi_s))

story.append(Paragraph(b("History of Critical Care Nursing"), h2_s))
hist_data = [
    [b('Era'), b('Key Event')],
    ['Early Origins (Crimean War)', 'Florence Nightingale observed critically ill patients needed close observation and grouping together — led to the idea of specialized care areas.'],
    ['20th Century', 'Polio epidemic → respiratory failure → mechanical ventilation introduced → specialized monitoring units emerged.'],
    ['1952 — Birth of ICUs', 'First modern ICU established in Copenhagen during polio epidemic. Patients grouped for continuous monitoring and mechanical ventilation.'],
    ['1960s–1970s', 'Expansion of ICUs worldwide. Development of cardiac care units (CCUs). American Association of Critical-Care Nurses (AACN) founded in 1969.'],
    ['Modern Era', 'Advanced life support technologies, specialized training, evidence-based care. Subspecialties: pediatric, neonatal, cardiothoracic critical care.'],
]
story.append(make_table(hist_data, [1.5*inch, 5.0*inch]))
story.append(Spacer(1, 4))
story.append(Paragraph("MCQ TIP: First modern ICU = 1952, Copenhagen, during polio epidemic. AACN founded = 1969. Florence Nightingale = Crimean War origins.", mcq_s))

story.append(PageBreak())

# ============================================================
# SECTION 2: THE INTENSIVE CARE NURSE
# ============================================================
story.append(Paragraph("  SECTION 2: THE INTENSIVE CARE NURSE", h1_s))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Definition"), h2_s))
story.append(Paragraph('An ICU nurse is a registered nurse with advanced knowledge/skills in caring for patients with life-threatening conditions, multi-organ dysfunction, and unstable vital signs. Works in ICU, HDU, emergency and trauma units.', body_s))

story.append(Paragraph(b("Roles of the ICU Nurse"), h2_s))
roles = [
    ("Patient Monitoring", "Continuous observation of HR, BP, RR, O2 saturation using advanced equipment."),
    ("Clinical Care & Interventions", "Administer medications (vasopressors, sedatives), manage mechanical ventilation, perform suctioning, IV line care, catheter management."),
    ("Rapid Decision-Making", "Recognize early signs of deterioration, respond to emergencies (cardiac arrest), initiate life-saving interventions."),
    ("Coordination of Care", "Work with multidisciplinary team: doctors, pharmacists, respiratory therapists. Ensure continuity of care."),
    ("Patient & Family Support", "Emotional/psychological support, educate families, assist with end-of-life decisions."),
    ("Infection Prevention & Control", "Maintain strict aseptic techniques, prevent HAIs, monitor for infection signs."),
]
for role, desc in roles:
    story.append(Paragraph(f'<bullet>&bull;</bullet> {b(role)}: {desc}', bullet_s))

story.append(Paragraph(b("Responsibilities"), h2_s))
story.append(Paragraph("Accurate documentation | Safe use of medical equipment | Maintaining patient safety | Advocacy for patient needs | Ethical and legal accountability", hi_s))

story.append(Paragraph(b("Skills Required"), h2_s))
skills_data = [
    [b('Skill Type'), b('Examples')],
    ['Technical', 'Operation of ventilators and monitors; interpretation of ECG and lab results; administration of critical medications'],
    ['Cognitive', 'Critical thinking; clinical judgment; problem-solving'],
    ['Interpersonal', 'Communication; teamwork; compassion and empathy'],
    ['Emotional Resilience', 'Coping with stress; managing grief and loss; maintaining professionalism under pressure'],
]
story.append(make_table(skills_data, [1.5*inch, 5.0*inch]))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Qualities of a Good ICU Nurse"), h2_s))
story.append(Paragraph("Vigilance and attention to detail | Quick responsiveness | Strong ethical values | Patience and dedication | Lifelong learner attitude", hi_s))

story.append(Paragraph(b("Challenges Faced by ICU Nurses"), h2_s))
for c in ["High workload and stress", "Emotional strain from critically ill patients", "Risk of burnout", "Exposure to infectious diseases", "Ethical dilemmas (e.g., end-of-life care)"]:
    story.append(Paragraph(f'<bullet>&bull;</bullet> {c}', bullet_s))

story.append(Paragraph("MCQ TIP: ICU nurse-to-patient ratio = 1:1 or 1:2. Educational requirement = RN + specialized critical care training + AACN certification.", mcq_s))

story.append(PageBreak())

# ============================================================
# SECTION 3: THE CRITICALLY ILL CLIENT
# ============================================================
story.append(Paragraph("  SECTION 3: THE CRITICALLY ILL CLIENT", h1_s))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Definition"), h2_s))
story.append(Paragraph('A critically ill client is an individual with actual or potential life-threatening organ dysfunction requiring intensive monitoring and support. WHO: severe health conditions needing immediate intervention to sustain life.', body_s))

story.append(Paragraph(b("Characteristics"), h2_s))
chars = [
    ("Physiological Instability", "Unstable vital signs, may need life-support, poor organ function"),
    ("High Risk of Deterioration", "Condition can worsen rapidly; needs constant observation"),
    ("Technology Dependence", "Ventilators, cardiac monitors, infusion pumps, dialysis machines"),
    ("Altered LOC", "Unconscious, sedated, or confused; reduced ability to communicate"),
    ("Complex Medical Needs", "Multiple IV medications, frequent diagnostic tests, multidisciplinary care"),
    ("Impaired Mobility", "Bedridden; risk of pressure ulcers, muscle wasting, blood clots"),
    ("Psychological/Emotional Stress", "Fear, anxiety, confusion, delirium; family members also stressed"),
]
for char, desc in chars:
    story.append(Paragraph(f'<bullet>&bull;</bullet> {b(char)}: {desc}', bullet_s))

story.append(Paragraph(b("Conditions Leading to Critical Illness"), h2_s))
story.append(Paragraph("Severe infections (sepsis) | Respiratory failure | Cardiac arrest | Trauma (accidents, injuries) | Stroke | Multi-organ failure", hi_s))

story.append(Paragraph(b("Physiological Changes by System"), h2_s))
phys_data = [
    [b('System'), b('Changes')],
    ['Respiratory', 'Difficulty breathing, reduced oxygenation, need for O2 therapy or mechanical ventilation'],
    ['Cardiovascular', 'Hypotension or hypertension, irregular heart rhythms, poor tissue perfusion'],
    ['Neurological', 'Confusion or coma, reduced responsiveness, increased intracranial pressure'],
    ['Renal', 'Reduced urine output, fluid and electrolyte imbalance'],
    ['Gastrointestinal', 'Reduced digestion, risk of bleeding or ulcers'],
]
story.append(make_table(phys_data, [1.5*inch, 5.0*inch]))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Patient Needs in Critical Illness"), h2_s))
needs_data = [
    [b('Need Type'), b('Details')],
    ['Physical', 'Airway support; adequate oxygenation; fluid/electrolyte balance; nutrition; hygiene; prevent complications'],
    ['Psychological', 'Reassurance; reduce fear/anxiety; orientation (for confused patients)'],
    ['Social', 'Family interaction; maintaining dignity and respect'],
    ['Spiritual', 'Support based on beliefs; access to spiritual care'],
    ['Safety', 'Protection from harm and infection; safe environment'],
]
story.append(make_table(needs_data, [1.5*inch, 5.0*inch]))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Family Needs in Critical Care"), h2_s))
fam_data = [
    [b('Need'), b('Details')],
    ['Information', 'Clear, honest, regular updates about patient condition; explanation of procedures'],
    ['Emotional Support', 'Counseling, reassurance, help coping with fear and uncertainty'],
    ['Involvement in Care', 'Participation in decision-making; opportunity to visit and support patient'],
    ['Comfort', 'Waiting areas, rest spaces, access to food and water'],
    ['Communication', 'Treated with empathy; opportunity to ask questions'],
]
story.append(make_table(fam_data, [1.5*inch, 5.0*inch]))

story.append(Paragraph("MCQ TIP: ABCDE approach in primary assessment: A=Airway, B=Breathing, C=Circulation, D=Disability (neuro), E=Exposure. Family needs are a distinct exam topic.", mcq_s))

story.append(PageBreak())

# ============================================================
# SECTION 4: THE ICU
# ============================================================
story.append(Paragraph("  SECTION 4: THE ICU — FEATURES, ENVIRONMENT &amp; QUALITY OF CARE", h1_s))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Definition of ICU"), h2_s))
story.append(Paragraph('A specialized hospital unit designed to provide continuous, intensive care for critically ill patients.', body_s))

story.append(Paragraph(b("Key Features of the ICU"), h2_s))
icu_data = [
    [b('Feature'), b('Details')],
    ['Advanced Monitoring', 'Continuous monitoring of heart rate, BP, oxygen levels; immediate detection of changes'],
    ['Specialized Equipment', 'Mechanical ventilators, cardiac monitors, dialysis machines, infusion pumps'],
    ['Highly Skilled Staff', 'Specialized nurses, intensivists (doctors), pharmacists, respiratory therapists'],
    ['Low Nurse-Patient Ratio', '1 nurse to 1-2 patients for close observation'],
    ['24-Hour Care', 'Continuous care and supervision; immediate emergency response'],
]
story.append(make_table(icu_data, [1.8*inch, 4.7*inch]))
story.append(Spacer(1, 4))

story.append(Paragraph(b("ICU Environment"), h2_s))
story.append(Paragraph("Quiet but highly controlled | Bright lights and machine alarms | Strict infection control | Patients admitted when needing intensive monitoring/life support; discharged when condition stabilizes", hi_s))

story.append(Paragraph(b("Qualities of Care for Critically Ill Clients"), h2_s))
qoc_data = [
    [b('Quality'), b('Meaning')],
    ['Holistic Care', 'Address physical, emotional, psychological, and spiritual needs; treat whole person'],
    ['Patient-Centered Care', 'Respect dignity, values, and preferences; involve family when appropriate'],
    ['Continuous Monitoring', 'Frequent vital signs assessment; early detection of complications'],
    ['Timely Intervention', 'Quick response to emergencies; proper medication/treatment administration'],
    ['Effective Communication', 'Clear communication within healthcare team and with patient/family'],
    ['Safety & Infection Control', 'Hygiene, sterile techniques; prevent HAIs'],
    ['Competence & Skill', 'Well-trained providers; ability to use advanced equipment'],
    ['Compassion & Empathy', 'Emotional support; kindness and understanding'],
    ['Ethical & Legal Responsibility', 'Confidentiality, patient rights, informed consent'],
    ['Teamwork & Collaboration', 'Coordination among all healthcare providers; shared decision-making'],
]
story.append(make_table(qoc_data, [1.8*inch, 4.7*inch]))

story.append(PageBreak())

# ============================================================
# SECTION 5: COMMON PROBLEMS
# ============================================================
story.append(Paragraph("  SECTION 5a: RESPIRATORY PROBLEMS", h1_s))
story.append(Spacer(1, 4))

resp_data = [
    [b('Problem'), b('Description'), b('Management')],
    ['Respiratory Failure', 'Inability to maintain adequate oxygenation or ventilation', 'Oxygen therapy or mechanical ventilation'],
    ['ARDS (Acute Respiratory Distress Syndrome)', 'Severe lung inflammation; reduced oxygen exchange', 'Mechanical ventilation; prone positioning; lung-protective strategies'],
    ['Airway Obstruction', 'Caused by secretions, swelling, or foreign bodies', 'Suctioning; airway adjuncts; emergency intubation if needed'],
    ['Ventilator-Associated Complications', 'Pneumonia (VAP); lung injury', 'Prevention bundle: HOB elevation, oral care, daily sedation vacation'],
]
story.append(make_table(resp_data, [1.5*inch, 2.3*inch, 2.7*inch]))

story.append(Spacer(1, 10))
story.append(Paragraph("  SECTION 5b: CARDIOVASCULAR PROBLEMS — SHOCK", h1_s))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Definition of Shock"), h2_s))
story.append(Paragraph('Shock is a life-threatening emergency where the body fails to deliver enough oxygen to tissues and organs. State of widespread reduced tissue perfusion. Without rapid treatment → irreversible organ damage or death.', body_s))

story.append(Paragraph(b("Types of Shock — Quick Comparison"), h2_s))
shock_data = [
    [b('Type'), b('Cause / Key Idea'), b('Skin'), b('Pulse'), b('Key Clue')],
    ['Hypovolemic', 'Loss of blood/fluid — "Tank is empty"', 'Cold, clammy', 'Fast, weak', 'Bleeding, burns, dehydration'],
    ['Cardiogenic', 'Heart pump failure — "Pump broken"', 'Cold, clammy', 'Weak/irregular', 'Heart attack; fluid in lungs'],
    ['Septic', 'Severe infection — "Vessels dilate/leak"', 'Warm → cold', 'Fast', 'Known infection (fever)'],
    ['Anaphylactic', 'Severe allergy — "Airway + vessels affected"', 'Flushed, hives', 'Fast', 'Minutes after allergen exposure'],
    ['Neurogenic', 'Spinal cord injury — "Loss of nerve control"', 'Warm, dry', 'SLOW (key!)', 'Recent spinal trauma'],
    ['Obstructive', 'Blocked blood flow (PE, cardiac tamponade)', 'Pale', 'Fast', 'Distended neck veins'],
]
story.append(make_table(shock_data, [1.0*inch, 1.7*inch, 1.0*inch, 0.8*inch, 1.9*inch]))
story.append(Spacer(1, 4))
story.append(Paragraph("MCQ TIP: Neurogenic shock is the ONLY type with SLOW pulse (bradycardia) + warm dry skin. Septic shock starts with WARM skin (early). Anaphylaxis = sudden onset after allergen. All other shocks = cold, clammy skin.", mcq_s))

story.append(Paragraph(b("Shock Symptoms to Watch For"), h2_s))
for s in ["Low blood pressure (weak pulse)", "Cold, clammy, pale skin", "Rapid but weak pulse", "Rapid breathing or difficulty breathing", "Confusion, anxiety, or loss of consciousness", "Low or no urine output"]:
    story.append(Paragraph(f'<bullet>&bull;</bullet> {s}', bullet_s))

story.append(Paragraph(b("Emergency First Aid for Shock"), h2_s))
for i, step in enumerate(["Call emergency services immediately (dial 112 in Cameroon).", "Lay person flat and elevate legs (unless injury prevents this).", "Check airway, breathing, circulation; start CPR if needed.", "Keep them warm with blanket; loosen tight clothing.", "Do NOT give food or drink.", "Turn on their side if vomiting (unless spinal injury suspected)."]):
    story.append(Paragraph(f'<bullet>{i+1}.</bullet> {step}', bullet_s))

story.append(Spacer(1, 6))
story.append(Paragraph(b("Arrhythmias"), h2_s))
story.append(Paragraph('Arrhythmia (dysrhythmia): irregular heartbeat due to faulty electrical signals. Normal HR = 60–100 bpm. Tachycardia >100 bpm; Bradycardia <60 bpm.', body_s))

arr_data = [
    [b('Type'), b('Description'), b('Risk')],
    ['Tachycardia', 'HR >100 bpm', 'Palpitations, dizziness, stroke risk'],
    ['Bradycardia', 'HR <60 bpm', 'Fainting, fatigue'],
    ['Atrial Fibrillation (AFib)', 'Chaotic atrial signals', 'Major stroke risk'],
    ['Ventricular Tachycardia', 'Fast ventricular rhythm', 'Life-threatening'],
    ['Ventricular Fibrillation', 'Chaotic ventricular signals', 'IMMEDIATE cardiac arrest — most dangerous'],
    ['PACs/PVCs', 'Extra beats', 'Usually harmless; can trigger arrhythmias'],
]
story.append(make_table(arr_data, [1.6*inch, 2.0*inch, 2.9*inch]))
story.append(Spacer(1, 4))
story.append(Paragraph("MCQ TIP: Ventricular fibrillation = most dangerous arrhythmia → immediate cardiac arrest → CPR + defibrillation. AFib = major stroke risk. Harmless arrhythmias = PACs, PVCs (occasional), sinus arrhythmia.", mcq_s))

story.append(PageBreak())

story.append(Paragraph("  SECTION 5c: NEUROLOGICAL PROBLEMS", h1_s))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Common Neurological Problems"), h2_s))
for p in ["Altered level of consciousness (LOC)", "Delirium", "Seizures / Status epilepticus", "Stroke (ischemic or hemorrhagic)", "Traumatic brain injury (TBI)", "Increased intracranial pressure (ICP)", "Hypoxic-ischemic encephalopathy", "Neuromuscular disorders (e.g., critical illness polyneuropathy)"]:
    story.append(Paragraph(f'<bullet>&bull;</bullet> {p}', bullet_s))

story.append(Paragraph(b("Glasgow Coma Scale (GCS)"), h2_s))
gcs_data = [
    [b('Component'), b('Score'), b('Response')],
    ['Eye Opening (E)', '4', 'Spontaneous'],
    ['', '3', 'To voice'],
    ['', '2', 'To pain'],
    ['', '1', 'None'],
    ['Verbal Response (V)', '5', 'Oriented'],
    ['', '4', 'Confused'],
    ['', '3', 'Inappropriate words'],
    ['', '2', 'Incomprehensible sounds'],
    ['', '1', 'None'],
    ['Motor Response (M)', '6', 'Obeys commands'],
    ['', '5', 'Localizes pain'],
    ['', '4', 'Withdraws from pain'],
    ['', '3', 'Flexion (decorticate)'],
    ['', '2', 'Extension (decerebrate)'],
    ['', '1', 'None'],
]
story.append(make_table(gcs_data, [1.8*inch, 0.8*inch, 3.9*inch]))
story.append(Paragraph("Max GCS = 15 (fully conscious). Min = 3 (deep coma). GCS ≤8 = severe; consider intubation.", mn_s))

story.append(Paragraph(b("Increased ICP — Cushing's Triad (CRITICAL MCQ)"), h2_s))
story.append(Paragraph("Cushing's Triad = Hypertension + Bradycardia + Irregular respiration. ICP >20 mmHg is pathological. Causes: TBI, hemorrhage, tumors, cerebral edema. Management: Head elevation 30°, sedation, osmotic agents (mannitol), controlled ventilation, surgical decompression.", hi_s))

neuro_data = [
    [b('Condition'), b('Key Causes'), b('Diagnosis Tool'), b('Management')],
    ['Altered LOC', 'Stroke, metabolic, sepsis, toxins', 'GCS, labs, CT/MRI, EEG', 'ABCs, correct reversible causes'],
    ['Delirium', 'Sepsis, hypoxia, drugs, ICU environment', 'CAM-ICU, ICDSC', 'Non-pharmacological bundle; treat cause'],
    ['Raised ICP', 'TBI, hemorrhage, stroke, tumors', 'Clinical signs, CT/MRI, ICP monitoring', 'Osmotherapy, hyperventilation, surgery'],
]
story.append(make_table(neuro_data, [1.2*inch, 1.5*inch, 1.5*inch, 2.3*inch]))
story.append(Spacer(1, 4))
story.append(Paragraph("MCQ TIP: Cushing's triad = hypertension + bradycardia + irregular breathing (sign of raised ICP). Delirium screening in ICU uses CAM-ICU. Decorticate = arms flex; decerebrate = arms extend (worse sign).", mcq_s))

story.append(PageBreak())

story.append(Paragraph("  SECTION 5d: RENAL PROBLEMS", h1_s))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Acute Kidney Injury (AKI)"), h2_s))
story.append(Paragraph(f'{b("KDIGO Criteria")}: Serum creatinine ↑ ≥0.3 mg/dL within 48h, OR ≥1.5× baseline within 7 days, OR urine output <0.5 mL/kg/h for ≥6h.', body_s))

aki_data = [
    [b('Type'), b('Causes')],
    ['Pre-renal', 'Hypovolemia, hypotension, sepsis, shock, renal hypoperfusion'],
    ['Intrinsic Renal', 'Acute tubular necrosis (ischemia, toxins), glomerulonephritis, interstitial nephritis'],
    ['Post-renal', 'Obstruction (stones, tumors, catheter blockage)'],
]
story.append(make_table(aki_data, [1.5*inch, 5.0*inch]))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Management of AKI"), h2_s))
for m in ["Optimize hemodynamics (fluids, vasopressors)", "Avoid nephrotoxins (NSAIDs, aminoglycosides, contrast)", "Adjust drug dosing to renal function", "Renal replacement therapy (RRT) indications: severe acidosis, hyperkalemia, fluid overload, uremic complications", "RRT modalities: intermittent hemodialysis or continuous RRT (CRRT)"]:
    story.append(Paragraph(f'<bullet>&bull;</bullet> {m}', bullet_s))

story.append(Paragraph(b("Fluid & Electrolyte Imbalances"), h2_s))
elec_data = [
    [b('Electrolyte'), b('Imbalance'), b('Cause'), b('Management')],
    ['Sodium', 'Hyponatremia', 'SIADH, fluid overload', 'Slow correction with hypertonic saline if symptomatic'],
    ['Sodium', 'Hypernatremia', 'Dehydration, diabetes insipidus', 'Gradual fluid replacement'],
    ['Potassium', 'Hyperkalemia', 'AKI, tissue breakdown', 'Calcium gluconate, insulin+glucose, dialysis if severe'],
    ['Potassium', 'Hypokalemia', 'Diuretics, GI losses', 'IV/oral potassium replacement'],
    ['Calcium', 'Hypocalcemia', 'Sepsis, pancreatitis', 'IV calcium replacement'],
]
story.append(make_table(elec_data, [0.9*inch, 1.1*inch, 1.5*inch, 2.9*inch]))
story.append(Spacer(1, 4))
story.append(Paragraph("MCQ TIP: AKI affects 30-60% of ICU patients. Hyperkalemia = most life-threatening electrolyte disorder (causes arrhythmias). Nephrotoxins to avoid: NSAIDs, aminoglycosides, contrast dye.", mcq_s))

story.append(PageBreak())

story.append(Paragraph("  SECTION 5e: GASTROINTESTINAL PROBLEMS", h1_s))
story.append(Spacer(1, 4))

gi_data = [
    [b('Problem'), b('Causes'), b('Diagnosis'), b('Management')],
    ['Malnutrition', 'Critical illness, prolonged fasting, malabsorption, increased metabolic demand', 'Weight loss, low albumin; screening tools: NRS-2002, MUST', 'Early enteral nutrition (within 24-48h); parenteral if enteral not possible; monitor for refeeding syndrome'],
    ['Stress Ulcers', 'Severe illness, mechanical ventilation >48h, coagulopathy, mucosal ischemia', 'Hematemesis, melena, anemia; endoscopy confirms', 'Prophylaxis: PPIs or H2 blockers in high-risk patients; endoscopic hemostasis if bleeding'],
    ['Constipation', 'Opioids, immobility, dehydration, reduced gut motility', 'Infrequent stools, abdominal distension', 'Laxatives (stimulant/osmotic); hydration; early mobilization; minimize opioids'],
    ['Diarrhea', 'Enteral feeding intolerance, C. difficile, antibiotics', 'Frequent loose stools, dehydration, electrolyte imbalance', 'Identify cause; hydration; adjust enteral feeding; infection control'],
]
story.append(make_table(gi_data, [1.0*inch, 1.5*inch, 1.3*inch, 2.7*inch]))
story.append(Spacer(1, 4))
story.append(Paragraph("MCQ TIP: Enteral nutrition is PREFERRED over parenteral (if feasible). Stress ulcer prophylaxis = PPIs or H2 blockers. Refeeding syndrome = hypophosphatemia + hypokalemia + hypomagnesemia.", mcq_s))

story.append(PageBreak())

story.append(Paragraph("  SECTION 5f: INFECTION PROBLEMS", h1_s))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Sepsis"), h2_s))
story.append(Paragraph('Life-threatening organ dysfunction caused by dysregulated host response to infection. Septic shock = subset with profound circulatory, cellular, and metabolic abnormalities.', body_s))
story.append(Paragraph(f'{b("Screening tools")}: qSOFA (hypotension + altered mentation + tachypnea); SOFA score (organ dysfunction).', body_s))
story.append(Paragraph(f'{b("Sepsis Bundle (within 1 hour)")}: Obtain cultures → Administer antibiotics → IV fluid resuscitation (30 mL/kg crystalloid) → Vasopressors (norepinephrine) if hypotension persists.', mn_s))

story.append(Paragraph(b("Hospital-Acquired Infections (HAIs)"), h2_s))
story.append(Paragraph('Infections not present at admission, occurring ≥48 hours after hospitalization.', body_s))
hai_data = [
    [b('Type'), b('Risk Factor'), b('Prevention')],
    ['VAP (Ventilator-Associated Pneumonia)', 'Endotracheal intubation', 'HOB elevation 30-45°, oral care, daily sedation vacation, early weaning'],
    ['CAUTI (Catheter-Associated UTI)', 'Urinary catheters', 'Remove early; aseptic insertion; closed drainage system'],
    ['CLABSI (Central Line Bloodstream Infection)', 'Central venous catheters', 'Sterile insertion technique; daily review for removal need'],
    ['SSI (Surgical Site Infection)', 'Surgery', 'Pre-op antibiotics; sterile technique; wound care'],
]
story.append(make_table(hai_data, [1.4*inch, 1.4*inch, 3.7*inch]))
story.append(Spacer(1, 4))
story.append(Paragraph("MCQ TIP: HAIs occur ≥48h after admission. Most common HAI in ICU = VAP. Norepinephrine = first-line vasopressor for septic shock. Sepsis bundle = within 1 HOUR.", mcq_s))

story.append(PageBreak())

story.append(Paragraph("  SECTION 5g: OTHER PROBLEMS", h1_s))
story.append(Spacer(1, 4))

other_data = [
    [b('Problem'), b('Causes'), b('Management')],
    ['Pressure Ulcers (Bedsores)', 'Prolonged immobility, poor perfusion', 'Reposition every 2h; pressure-relieving devices; skin hygiene'],
    ['Muscle Wasting', 'Immobility, critical illness', 'Early passive/active exercises; physiotherapy'],
    ['DVT (Deep Vein Thrombosis)', 'Immobility, blood clots', 'Prophylactic anticoagulation; compression stockings; early mobilization'],
    ['ICU Delirium', 'Noise, sleep deprivation, medications, sepsis', 'CAM-ICU screening; reorientation; minimize sedation; family visits'],
    ['Anxiety/Depression', 'ICU environment, illness, uncertainty', 'Reassurance; counseling; involve family'],
    ['Communication Problems', 'Intubation (unable to speak), weakness', 'Writing boards; picture boards; lip reading; alternative communication'],
    ['Sleep Disturbances', 'Noise, lights, frequent procedures', 'Cluster care activities; reduce noise; dim lights at night'],
    ['Pain', 'Illness, procedures, immobility', 'Regular pain assessment; analgesics; comfort positioning'],
]
story.append(make_table(other_data, [1.4*inch, 1.5*inch, 3.6*inch]))

story.append(PageBreak())

# ============================================================
# SECTION 6: MONITORING
# ============================================================
story.append(Paragraph("  SECTION 6: MONITORING THE CRITICALLY ILL CLIENT", h1_s))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Purpose of Monitoring"), h2_s))
story.append(Paragraph("Detect early signs of deterioration | Guide treatment | Evaluate response to therapy | Maintain vital functions | Prevent complications", hi_s))

mon_data = [
    [b('Type'), b('What it Assesses'), b('Tools/Methods')],
    ['Clinical (Physical)', 'LOC, skin color/temp, capillary refill, urine output, pain', 'GCS, direct observation'],
    ['Vital Signs', 'Temperature, pulse, BP, respiratory rate', 'Thermometer, BP cuff, monitors'],
    ['Hemodynamic', 'Cardiovascular function and blood flow', 'Non-invasive: BP cuff, pulse oximeter; Invasive: arterial line, CVP'],
    ['Respiratory', 'Oxygenation, ventilation', 'SpO2 (pulse oximeter), ABG, ventilator parameters'],
    ['Cardiac', 'Heart rhythm and rate', 'Continuous ECG monitoring'],
    ['Neurological', 'Consciousness, ICP signs', 'GCS, pupillary response, Cushing\'s triad monitoring'],
    ['Renal', 'Kidney function, fluid balance', 'Urine output charting, urea/creatinine blood tests'],
    ['Laboratory', 'Blood chemistry, infection markers', 'Electrolytes, Hb, WBC, glucose, ABG'],
]
story.append(make_table(mon_data, [1.3*inch, 1.8*inch, 3.4*inch]))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Nursing Responsibilities in Monitoring"), h2_s))
for nr in ["Perform frequent and accurate assessments", "Record vital signs and document changes accurately", "Understand normal vs abnormal values; recognize trends", "Report abnormal findings immediately to healthcare team", "Ensure proper functioning and hygiene of monitoring devices"]:
    story.append(Paragraph(f'<bullet>&bull;</bullet> {nr}', bullet_s))

story.append(Paragraph(b("Principles of Effective Monitoring"), h2_s))
story.append(Paragraph("Continuous and consistent | Accurate and timely | Patient-centered | Use both technology AND clinical judgment | Early intervention based on findings", hi_s))

story.append(Paragraph(b("Complications of Monitoring"), h2_s))
story.append(Paragraph("Infection (especially invasive monitoring) | Equipment malfunction | Misinterpretation of data | Patient discomfort", hi_s))

story.append(PageBreak())

# ============================================================
# SECTION 7: NURSING CARE PLAN
# ============================================================
story.append(Paragraph("  SECTION 7: NURSING CARE PLAN OF THE CRITICALLY ILL CLIENT", h1_s))
story.append(Spacer(1, 4))

story.append(Paragraph(b("Goals of Nursing Care"), h2_s))
story.append(Paragraph("Maintain ABC | Stabilize vital functions | Prevent complications | Provide comfort/pain relief | Support psychological well-being | Promote recovery and rehabilitation", hi_s))

story.append(Paragraph(b("Key Nursing Interventions by Domain"), h2_s))
interv_data = [
    [b('Domain'), b('Interventions')],
    ['Airway & Breathing', 'Maintain patency (position, suction); oxygen therapy; assist ventilation; monitor SpO2'],
    ['Circulatory Support', 'Monitor vital signs; administer IV fluids/medications; observe for shock signs'],
    ['Fluid & Electrolytes', 'Monitor I&O; assess for dehydration/overload; administer fluids as prescribed'],
    ['Pain Management', 'Assess pain regularly; administer analgesics; positioning; calm environment'],
    ['Nutrition', 'Enteral or parenteral feeding; monitor nutritional status; prevent aspiration'],
    ['Infection Control', 'Hand hygiene; aseptic technique; wound/IV line care; monitor for infection'],
    ['Skin & Pressure Ulcer', 'Reposition every 2 hours; skin hygiene; pressure-relieving devices'],
    ['Mobility', 'Passive/active exercises; prevent DVT, muscle wasting'],
    ['Neurological', 'Monitor GCS; watch for raised ICP signs; maintain patient safety'],
    ['Psychological', 'Reassurance; reduce anxiety; orient confused patients'],
    ['Communication', 'Clear communication; alternative methods (writing boards) for intubated patients'],
    ['Family Care', 'Regular updates; emotional support; involve in care; respect cultural beliefs'],
]
story.append(make_table(interv_data, [1.5*inch, 5.0*inch]))
story.append(Spacer(1, 6))

story.append(Paragraph(b("Nursing Care Plan — Summary Table"), h2_s))
ncp_data = [
    [b('Nursing Diagnosis'), b('Goal'), b('Interventions'), b('Rationale')],
    ['Impaired Gas Exchange r/t respiratory failure', 'Maintain SpO2 >94%', 'Monitor RR & SpO2; O2 therapy; semi-Fowler\'s position; assist ventilation', 'Detects hypoxia; improves O2 delivery; enhances lung expansion'],
    ['Decreased Cardiac Output r/t circulatory failure', 'Stable vital signs', 'Monitor BP, pulse, ECG; IV fluids/meds; assess for shock', 'Evaluates heart function; maintains perfusion'],
    ['Risk for Infection r/t invasive procedures', 'No infection', 'Hand hygiene; aseptic technique; monitor temp & WBC; IV/catheter care', 'Prevents microorganism spread; early detection'],
    ['Acute Pain r/t illness/procedures', 'Reduced pain', 'Assess pain; administer analgesics; comfort measures', 'Ensures pain control; promotes relaxation'],
    ['Imbalanced Nutrition: Less than Body Req.', 'Adequate nutrition', 'Enteral/parenteral feeding; monitor weight/labs; prevent aspiration', 'Adequate nutrients; supports healing'],
    ['Impaired Skin Integrity r/t immobility', 'Intact skin', 'Reposition q2h; skin hygiene; pressure devices', 'Prevents pressure ulcers; promotes circulation'],
    ['Risk for Fluid Volume Imbalance', 'Normal fluid balance', 'Monitor I&O; assess edema/dehydration; fluids as prescribed', 'Detects imbalance; maintains homeostasis'],
    ['Anxiety r/t critical condition', 'Reduced anxiety', 'Emotional support; clear information; family involvement', 'Reduces fear; builds trust'],
    ['Impaired Physical Mobility', 'Optimal mobility', 'Passive/active exercises; reposition; prevent DVT', 'Prevents immobility complications'],
]
story.append(make_table(ncp_data, [1.4*inch, 1.0*inch, 2.1*inch, 2.0*inch]))

story.append(PageBreak())

# ============================================================
# SECTION 8: MCQ TIPS & PRACTICE
# ============================================================
story.append(Paragraph("  SECTION 8: MCQ TIPS &amp; PRACTICE QUESTIONS", h1_s))
story.append(Spacer(1, 6))

story.append(Paragraph(b("Top MCQ Traps — NUS406"), h2_s))
traps = [
    ("First modern ICU", "1952, Copenhagen, Denmark, during the POLIO epidemic — not World War I or II."),
    ("AACN Founded", "1969 — American Association of Critical-Care Nurses."),
    ("Neurogenic shock pulse", "SLOW (bradycardia) + warm dry skin — opposite of all other shocks."),
    ("Septic shock early vs late", "Early septic shock = WARM, flushed skin. Late = cold, clammy (like other shocks)."),
    ("Ventricular fibrillation", "MOST dangerous arrhythmia → cardiac arrest → requires IMMEDIATE CPR + defibrillation."),
    ("Cushing's triad", "Hypertension + Bradycardia + Irregular respiration = sign of RAISED ICP (not cardiac shock)."),
    ("GCS maximum score", "15 (normal). Minimum = 3 (deep coma). ≤8 = severe; usually intubate."),
    ("HAI definition", "Infection NOT present at admission; occurs ≥48 HOURS after hospitalization."),
    ("Sepsis bundle timing", "WITHIN 1 HOUR — obtain cultures, antibiotics, fluids, vasopressors if needed."),
    ("AKI criteria", "Creatinine ↑ ≥0.3 mg/dL in 48h OR urine output <0.5 mL/kg/h for ≥6h."),
    ("Enteral vs parenteral", "Enteral nutrition = PREFERRED if gut works. Parenteral = only when enteral not possible."),
    ("Stress ulcer prophylaxis", "PPIs or H2 blockers — prevention is key, especially for ventilated patients >48h."),
    ("ICU nurse-patient ratio", "1:1 or 1:2 — this is a defining feature of ICU care."),
    ("ABCDE primary assessment", "A=Airway, B=Breathing, C=Circulation, D=Disability (neuro), E=Exposure."),
    ("Refeeding syndrome electrolytes", "Hypophosphatemia + hypokalemia + hypomagnesemia after refeeding a malnourished patient."),
]
for trap, explanation in traps:
    story.append(Paragraph(f'<bullet>&bull;</bullet> {b(trap)}: {explanation}', bullet_s))

story.append(Spacer(1, 8))
story.append(Paragraph(b("50 Practice MCQs with Answers &amp; Rationale"), h2_s))
story.append(Spacer(1, 4))

mcqs = [
    ("1. Critical care nursing is defined by the AACN as:",
     ["A. Nursing care for elderly patients only.", "B. The specialty that deals with human responses to life-threatening problems.", "C. Nursing care provided only in emergency departments.", "D. General nursing care for all hospital patients."],
     "B", "The AACN defines critical care nursing as the specialty dealing specifically with human responses to life-threatening problems."),
    ("2. The first modern ICU was established in:",
     ["A. 1940, London", "B. 1945, New York", "C. 1952, Copenhagen", "D. 1969, Washington D.C."],
     "C", "The first modern ICU was established in 1952 in Copenhagen, Denmark, during the polio epidemic, when patients needed ventilatory support."),
    ("3. Florence Nightingale's contribution to critical care was:",
     ["A. Inventing the ventilator", "B. Founding the AACN", "C. Observing that critically ill patients needed close monitoring and grouping", "D. Developing the ICU admission criteria"],
     "C", "During the Crimean War, Nightingale observed that critically ill patients needed close observation and grouping — laying the groundwork for specialized care areas."),
    ("4. The American Association of Critical-Care Nurses was founded in:",
     ["A. 1952", "B. 1960", "C. 1969", "D. 1975"],
     "C", "The AACN was founded in 1969 during the expansion of ICUs worldwide in the 1960s–1970s."),
    ("5. Which of the following is NOT a goal of critical care nursing?",
     ["A. Preserve life", "B. Restore health", "C. Perform surgery", "D. Assist in end-of-life care"],
     "C", "Goals of critical care nursing include preserving life, restoring health, preventing complications, providing comfort, and assisting in end-of-life care. Surgery is performed by surgeons, not nurses."),
    ("6. The typical nurse-to-patient ratio in the ICU is:",
     ["A. 1:5", "B. 1:3", "C. 1:1 to 1:2", "D. 1:10"],
     "C", "ICUs maintain a low nurse-patient ratio (1:1 or 1:2) for close observation, which is a defining feature of intensive care."),
    ("7. Which skill involves the ability to interpret ECG results and operate ventilators?",
     ["A. Cognitive skills", "B. Technical skills", "C. Interpersonal skills", "D. Emotional skills"],
     "B", "Technical skills in ICU nursing include operating ventilators and monitors, interpreting ECG and lab results, and administering critical medications."),
    ("8. A critically ill client is BEST defined as:",
     ["A. Any patient admitted to hospital", "B. A patient with mild illness needing observation", "C. A patient with actual or potential life-threatening organ dysfunction requiring intensive monitoring", "D. A patient recovering from surgery"],
     "C", "A critically ill client has actual or potential life-threatening organ dysfunction requiring intensive monitoring, advanced support, and specialized care."),
    ("9. Which is a characteristic specific to critically ill clients?",
     ["A. Stable vital signs", "B. Independence from medical technology", "C. Dependence on life-support systems like ventilators", "D. Full ability to communicate needs"],
     "C", "Critically ill clients characteristically depend on life-support systems such as ventilators, cardiac monitors, and infusion pumps."),
    ("10. The ABCDE approach to primary assessment stands for:",
     ["A. Airway, Blood, Chemistry, Diagnosis, Evaluation", "B. Airway, Breathing, Circulation, Disability, Exposure", "C. Assessment, Breathing, Circulation, Drugs, Examination", "D. Airway, Bones, Circulation, Documentation, Evaluation"],
     "B", "ABCDE = Airway (ensure clear), Breathing (assess effort), Circulation (pulse/BP), Disability (neurological), Exposure (full body exam)."),
    ("11. Family needs in critical care include all of the following EXCEPT:",
     ["A. Information about patient condition", "B. Emotional support and counseling", "C. Permission to perform nursing procedures", "D. Involvement in care and decision-making"],
     "C", "Family needs include information, emotional support, involvement in care, comfort, and respectful communication — not permission to perform nursing procedures."),
    ("12. Which type of shock is characterized by a SLOW pulse and warm, dry skin?",
     ["A. Hypovolemic", "B. Cardiogenic", "C. Neurogenic", "D. Septic"],
     "C", "Neurogenic shock (from spinal cord/brain injury) causes bradycardia (slow pulse) + warm, dry skin due to loss of sympathetic nerve control — the key distinguishing feature."),
    ("13. A patient is brought in after a road traffic accident with low BP and cold, clammy skin. Which type of shock is most likely?",
     ["A. Neurogenic", "B. Anaphylactic", "C. Hypovolemic", "D. Septic"],
     "C", "Hypovolemic shock from trauma (blood loss) presents with low BP, cold/clammy skin, rapid weak pulse — the 'empty tank' scenario."),
    ("14. Septic shock in its early stage is characterized by:",
     ["A. Cold, clammy skin", "B. Warm, flushed skin with low BP", "C. High BP", "D. Slow pulse"],
     "B", "Early septic shock presents with warm, flushed skin (vasodilation from infection) + low BP. Late stages progress to cold, clammy skin."),
    ("15. Anaphylactic shock occurs:",
     ["A. Hours after allergen exposure", "B. Days after infection", "C. Within minutes of allergen exposure", "D. Only in elderly patients"],
     "C", "Anaphylactic shock typically develops within minutes of exposure to an allergen (food, medication, insect sting)."),
    ("16. The most dangerous arrhythmia leading to immediate cardiac arrest is:",
     ["A. Sinus bradycardia", "B. Atrial fibrillation", "C. Premature ventricular contractions", "D. Ventricular fibrillation"],
     "D", "Ventricular fibrillation causes chaotic ventricular signals → no effective cardiac output → immediate cardiac arrest. Requires CPR + defibrillation."),
    ("17. A patient with a heart rate >100 bpm has:",
     ["A. Bradycardia", "B. Tachycardia", "C. Atrial fibrillation", "D. Heart block"],
     "B", "Tachycardia = heart rate >100 bpm. Bradycardia = <60 bpm. Normal = 60–100 bpm."),
    ("18. Which arrhythmia carries the highest risk of stroke?",
     ["A. Sinus bradycardia", "B. Premature atrial contractions", "C. Atrial fibrillation (AFib)", "D. Sinus tachycardia"],
     "C", "Atrial fibrillation causes chaotic atrial signals leading to blood pooling and clot formation in the atria, which can embolize to the brain causing stroke."),
    ("19. Cushing's Triad (sign of raised ICP) consists of:",
     ["A. Hypotension, tachycardia, shallow breathing", "B. Hypertension, bradycardia, irregular respiration", "C. Fever, tachycardia, hypotension", "D. Low BP, fast pulse, warm skin"],
     "B", "Cushing's Triad = Hypertension + Bradycardia + Irregular respiration. This is a late, ominous sign of severely raised intracranial pressure."),
    ("20. The maximum score on the Glasgow Coma Scale is:",
     ["A. 10", "B. 12", "C. 15", "D. 20"],
     "C", "GCS max = 15 (E4+V5+M6). Min = 3 (all no response). GCS ≤8 = severe brain injury; consider airway protection."),
    ("21. ICP is considered pathological when it exceeds:",
     ["A. 5 mmHg", "B. 10 mmHg", "C. 15 mmHg", "D. 20 mmHg"],
     "D", "Normal ICP = 7–15 mmHg. Sustained ICP >20 mmHg is pathological and can lead to brain herniation and death."),
    ("22. Delirium in the ICU is BEST screened using:",
     ["A. GCS alone", "B. CAM-ICU or ICDSC", "C. MRI", "D. EEG only"],
     "B", "CAM-ICU (Confusion Assessment Method for ICU) and ICDSC (Intensive Care Delirium Screening Checklist) are validated screening tools for ICU delirium."),
    ("23. Which of the following is a recommended position to reduce ICP?",
     ["A. Flat (supine)", "B. Trendelenburg (head down)", "C. Head of bed elevated at 30°", "D. Prone position"],
     "C", "Elevating the head of bed to 30° promotes venous drainage from the brain, reduces ICP. Trendelenburg would worsen it."),
    ("24. Acute Kidney Injury (AKI) is diagnosed when urine output falls below:",
     ["A. 1 mL/kg/h for 2h", "B. 0.5 mL/kg/h for ≥6h", "C. 2 mL/kg/h for 4h", "D. 0.1 mL/kg/h for 1h"],
     "B", "KDIGO AKI criteria include urine output <0.5 mL/kg/h for ≥6h, OR serum creatinine rise ≥0.3 mg/dL in 48h, OR ≥1.5× baseline within 7 days."),
    ("25. Which medication is CONTRAINDICATED in AKI due to nephrotoxicity?",
     ["A. Paracetamol", "B. NSAIDs", "C. Antihistamines", "D. Antacids"],
     "B", "NSAIDs (and aminoglycosides, contrast dye) are nephrotoxic and must be AVOIDED in AKI. They reduce renal blood flow by inhibiting prostaglandins."),
    ("26. The most life-threatening electrolyte imbalance in AKI is:",
     ["A. Hyponatremia", "B. Hypocalcemia", "C. Hyperkalemia", "D. Hypomagnesemia"],
     "C", "Hyperkalemia is the most immediately life-threatening electrolyte disorder in AKI because it can cause fatal cardiac arrhythmias. Treatment: calcium gluconate, insulin+glucose, dialysis."),
    ("27. Enteral nutrition is preferred over parenteral nutrition because:",
     ["A. It is cheaper and easier", "B. It maintains gut integrity, reduces infection risk, and has better outcomes", "C. It requires less monitoring", "D. It provides more calories"],
     "B", "Enteral nutrition (via gut) maintains intestinal barrier integrity, reduces bacterial translocation, and has fewer complications than parenteral. Preferred if gut is functional."),
    ("28. Which group of patients should receive stress ulcer prophylaxis?",
     ["A. All ICU patients", "B. Only post-surgical patients", "C. High-risk patients: mechanical ventilation >48h, coagulopathy", "D. Only patients with known peptic ulcer disease"],
     "C", "Stress ulcer prophylaxis is targeted to high-risk ICU patients: mechanical ventilation >48h, coagulopathy, severe illness. PPIs or H2 blockers are used."),
    ("29. Refeeding syndrome is characterized by:",
     ["A. Hyperkalemia, hyperphosphatemia, hypermagnesemia", "B. Hypophosphatemia, hypokalemia, hypomagnesemia", "C. Hypernatremia and hyperglycemia", "D. High albumin and weight gain"],
     "B", "Refeeding syndrome occurs when malnourished patients are re-fed too quickly. Insulin release shifts electrolytes into cells → hypophosphatemia (most hallmark), hypokalemia, hypomagnesemia."),
    ("30. Hospital-acquired infections (HAIs) are defined as infections occurring:",
     ["A. Within 24 hours of admission", "B. ≥48 hours after admission, not present at time of admission", "C. Only in ICU patients", "D. Only from surgical procedures"],
     "B", "HAIs (nosocomial infections) are infections not present/incubating at admission, developing ≥48 hours after hospitalization."),
    ("31. The most common VAP prevention measure is:",
     ["A. Prone positioning", "B. Head of bed elevation to 30-45° and daily oral care", "C. Immediate extubation", "D. Broad-spectrum antibiotics prophylactically"],
     "B", "VAP bundle includes: head of bed elevation (30-45°), daily oral decontamination, daily sedation vacation to assess extubation readiness, subglottic secretion drainage."),
    ("32. The sepsis bundle should be completed within:",
     ["A. 6 hours", "B. 3 hours", "C. 1 hour", "D. 24 hours"],
     "C", "Current Surviving Sepsis Campaign recommends completing the sepsis bundle (cultures, antibiotics, fluids, vasopressors) within 1 HOUR of sepsis recognition."),
    ("33. First-line vasopressor for septic shock is:",
     ["A. Dopamine", "B. Adrenaline (epinephrine)", "C. Norepinephrine", "D. Vasopressin"],
     "C", "Norepinephrine is the first-line vasopressor for septic shock per international guidelines (Surviving Sepsis Campaign)."),
    ("34. Which is a primary neurological problem (not secondary/systemic)?",
     ["A. Hypoglycemia-induced altered consciousness", "B. Sepsis-associated encephalopathy", "C. Ischemic stroke", "D. Drug overdose causing coma"],
     "C", "Stroke is a primary neurological cause. The others (hypoglycemia, sepsis, drugs) are secondary/systemic causes of altered consciousness."),
    ("35. Repositioning a critically ill patient should be done every:",
     ["A. 4 hours", "B. 6 hours", "C. 2 hours", "D. 8 hours"],
     "C", "Patients should be repositioned every 2 hours to prevent pressure ulcers and promote circulation. This is a standard nursing intervention for immobile patients."),
    ("36. Which monitoring type assesses LOC using the Glasgow Coma Scale?",
     ["A. Hemodynamic monitoring", "B. Respiratory monitoring", "C. Neurological monitoring", "D. Laboratory monitoring"],
     "C", "Neurological monitoring includes LOC assessment (GCS), pupil size and reaction, and signs of increased ICP."),
    ("37. Central venous pressure (CVP) monitoring is classified as:",
     ["A. Clinical monitoring", "B. Non-invasive hemodynamic monitoring", "C. Invasive hemodynamic monitoring", "D. Laboratory monitoring"],
     "C", "CVP is an invasive hemodynamic monitoring method (requires central venous catheter). Non-invasive = BP cuff, pulse oximeter."),
    ("38. An ICU patient cannot speak because they are intubated. The BEST alternative communication method is:",
     ["A. Waiting until extubation", "B. Asking family to interpret", "C. Writing boards or picture boards", "D. Lip reading only"],
     "C", "For intubated patients who cannot speak, alternative communication tools include writing boards, picture/communication boards, eye-gaze systems, and electronic devices."),
    ("39. Which nursing diagnosis is MOST appropriate for a patient on mechanical ventilation?",
     ["A. Risk for falls", "B. Impaired gas exchange related to respiratory failure", "C. Constipation related to immobility", "D. Risk for social isolation"],
     "B", "A patient on mechanical ventilation has impaired gas exchange as the priority nursing diagnosis. The ventilator is being used because normal gas exchange is compromised."),
    ("40. What is the rationale for positioning a critically ill patient in semi-Fowler's position?",
     ["A. Reduces risk of falls", "B. Enhances lung expansion and improves oxygenation", "C. Prevents DVT", "D. Reduces pain"],
     "B", "Semi-Fowler's position (head of bed 30-45°) allows the diaphragm to descend, enhances lung expansion, improves oxygenation, and reduces aspiration risk."),
    ("41. The primary goal of nursing care for the critically ill is:",
     ["A. Document all medications administered", "B. Maintain airway, breathing, and circulation (ABC)", "C. Notify the family of diagnosis", "D. Prepare the patient for surgery"],
     "B", "The primary goal of nursing care for the critically ill is to maintain ABC (Airway, Breathing, Circulation) — the life-sustaining functions."),
    ("42. ICU delirium is BEST prevented by:",
     ["A. Increasing sedation doses", "B. Keeping the patient isolated", "C. Reorientation, sleep hygiene, early mobilization, family engagement", "D. Routine antipsychotic medications"],
     "C", "Non-pharmacological bundle for ICU delirium: reorientation (clocks, calendars), sleep hygiene, early mobilization, family visits, minimize sedation. Pharmacological options have limited evidence."),
    ("43. Which condition is caused by severe physiological stress and can lead to GI bleeding?",
     ["A. Stress ulcers", "B. Pressure ulcers", "C. Peptic ulcer disease", "D. Crohn's disease"],
     "A", "Stress ulcers are acute mucosal erosions in the stomach/duodenum occurring in critically ill patients due to severe physiological stress, hypoperfusion, and mucosal ischemia."),
    ("44. What does qSOFA stand for in sepsis screening?",
     ["A. Quick Sequential Organ Failure Assessment", "B. Quantitative Sepsis Fever Assessment", "C. Quick Sepsis Organ Function Analysis", "D. Quantitative Systematic Organ Failure Approach"],
     "A", "qSOFA = Quick Sequential [Sepsis-related] Organ Failure Assessment. Positive when ≥2 of: altered mentation, tachypnea (RR ≥22), hypotension (SBP ≤100)."),
    ("45. Deep vein thrombosis (DVT) in critically ill patients is caused by:",
     ["A. Excessive hydration", "B. Prolonged immobility", "C. High oxygen therapy", "D. Pain medication"],
     "B", "Prolonged immobility → venous stasis → blood clot formation in deep veins (DVT). Prevention: prophylactic anticoagulation, compression stockings, early mobilization."),
    ("46. A patient with a history of penicillin allergy develops sudden onset swelling of the lips, difficulty breathing, and low BP after receiving amoxicillin. This is:",
     ["A. Septic shock", "B. Hypovolemic shock", "C. Anaphylactic shock", "D. Cardiogenic shock"],
     "C", "Anaphylactic shock = sudden life-threatening allergic reaction. Classic features: rapid onset after allergen exposure, facial swelling, breathing difficulty, hives, low BP."),
    ("47. For a patient with raised ICP, which of the following should be AVOIDED?",
     ["A. Head elevation at 30°", "B. Osmotic diuretics (mannitol)", "C. Trendelenburg (head-down) position", "D. Sedation"],
     "C", "Trendelenburg position (head down) increases venous pressure in the head and worsens ICP. All other options help manage raised ICP."),
    ("48. An unconscious patient's eyes open only to pain. What is the eye-opening score on GCS?",
     ["A. 1", "B. 2", "C. 3", "D. 4"],
     "B", "GCS Eye Opening: 4=spontaneous, 3=to voice, 2=to pain, 1=none. Eyes opening only to pain = E2."),
    ("49. Which statement BEST describes holistic care in critical illness?",
     ["A. Focusing only on the patient's physical needs", "B. Treating only the disease, not the person", "C. Addressing physical, emotional, psychological, and spiritual needs of the patient", "D. Providing care only during emergencies"],
     "C", "Holistic care addresses ALL dimensions of the person: physical, emotional, psychological, and spiritual — treating the patient as a whole, not just the disease."),
    ("50. The primary reason for maintaining strict hand hygiene in the ICU is to:",
     ["A. Improve patient comfort", "B. Prevent hospital-acquired infections", "C. Reduce medication errors", "D. Maintain documentation accuracy"],
     "B", "Strict hand hygiene is the single most effective measure to prevent hospital-acquired infections (HAIs) in the ICU, where patients are highly vulnerable."),
]

for mcq in mcqs:
    question, options, answer, rationale = mcq
    story.append(Paragraph(b(question), body_s))
    for opt in options:
        letter = opt[0]
        is_correct = letter == answer
        color_hex = '#1a4731' if is_correct else '#333333'
        fn = 'Helvetica-Bold' if is_correct else 'Helvetica'
        opt_s = ParagraphStyle('OPT', parent=styles['Normal'], fontSize=10, leftIndent=18, spaceAfter=1, textColor=colors.HexColor(color_hex), fontName=fn, leading=13)
        story.append(Paragraph(opt + (" ✓" if is_correct else ""), opt_s))
    story.append(Paragraph(f"Rationale: {rationale}", note_s))
    story.append(Spacer(1, 6))

# QUICK REFERENCE LAST PAGE
story.append(PageBreak())
story.append(Paragraph("  QUICK REFERENCE — KEY NUMBERS &amp; FACTS", h1_s))
story.append(Spacer(1, 4))

qr_data = [
    [b('Fact'), b('Value / Detail')],
    ['First modern ICU', '1952, Copenhagen, polio epidemic'],
    ['AACN founded', '1969'],
    ['Normal heart rate', '60–100 bpm'],
    ['GCS max/min', '15 (normal) / 3 (deep coma)'],
    ['GCS ≤ 8', 'Severe brain injury → consider intubation'],
    ['Cushing\'s Triad', 'Hypertension + Bradycardia + Irregular respiration (raised ICP)'],
    ['Pathological ICP', '>20 mmHg'],
    ['Head elevation for ICP', '30° (reduces venous pressure in brain)'],
    ['ICU nurse-patient ratio', '1:1 or 1:2'],
    ['AKI urine output criterion', '<0.5 mL/kg/h for ≥6 hours'],
    ['AKI creatinine criterion', '↑ ≥0.3 mg/dL in 48h OR ≥1.5× baseline in 7 days'],
    ['Sepsis bundle timing', 'Within 1 HOUR'],
    ['Vasopressor for septic shock', 'Norepinephrine (first-line)'],
    ['Sepsis fluid resuscitation', '30 mL/kg crystalloid'],
    ['HAI definition', '≥48h after admission; not present at admission'],
    ['ICU delirium tools', 'CAM-ICU, ICDSC'],
    ['Enteral nutrition timing', 'Within 24–48h if feasible'],
    ['Repositioning frequency', 'Every 2 hours'],
    ['Refeeding syndrome', 'Hypophosphatemia + hypokalemia + hypomagnesemia'],
    ['VAP prevention (key)', 'HOB 30-45° + daily oral care + daily sedation vacation'],
    ['Most dangerous arrhythmia', 'Ventricular fibrillation → CPR + defibrillation'],
    ['AFib main risk', 'Stroke (clot formation in atria)'],
    ['Shock with slow pulse', 'Neurogenic shock (spinal injury)'],
    ['Shock with warm early skin', 'Septic shock (early stage)'],
    ['Emergency number (Cameroon)', '112'],
]
story.append(make_table(qr_data, [2.5*inch, 4.0*inch]))
story.append(Spacer(1, 12))
story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#ccc')))
story.append(Paragraph("NUS406 Intensive Care-Theatre Nursing | Prof. Eta Vivian Ayamba | Good luck on your exams!", ParagraphStyle('FT', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#888'), alignment=TA_CENTER, spaceBefore=6)))

doc.build(story)
print("PDF created successfully!")