from __future__ import annotations

"""Learner-display catalogue only.

This module is deliberately separate from Power House governed curriculum/catalogue
state.  It gives ScoreMax a complete browse surface while the first governed content
projection is being rectified.  Power House remains authoritative and can replace or
reconcile these labels later without changing question identity, readiness or release.
"""


def _items(start, names):
    return tuple({'number': str(start+i), 'name': name} for i, name in enumerate(names))


def _numbered(pairs):
    return tuple({'number': str(number), 'name': name} for number, name in pairs)


YEAR11 = {
    'label': 'Year 11 · Punjab',
    'collection_label': 'Chapters',
    'subjects': {
        'Biology': _items(1, (
            'Biodiversity and Classification',
            'Bacteria and Viruses',
            'Cells and Subcellular Organelles',
            'Molecular Biology',
            'Enzymes',
            'Bioenergetics',
            'Structural and Computational Biology',
            'Plant Physiology',
            'Human Digestive System',
            'Human Respiratory System',
            'Human Circulatory System',
            'Human Skeletal and Muscular Systems',
        )),
        'Chemistry': _items(1, (
            'Periodic Table and Periodic Properties',
            'Atomic Structure',
            'Chemical Bonding',
            'Stoichiometry',
            'States and Phases of Matter',
            'Chemical Energetics',
            'Reaction Kinetics',
            'Chemical Equilibrium',
            'Acid-Base Chemistry',
            'Electrochemistry',
            'Hydrocarbons',
            'Nitrogen and Sulfur',
            'Halogens',
            'Atmosphere',
            'Basic Separation Techniques',
            'Lab Safety and Practical Skills',
        )),
        'Physics': _items(1, (
            'Measurements',
            'Force and Motion',
            'Circular and Rotational Motion',
            'Work, Energy and Power',
            'Solids and Fluid Dynamics',
            'Heat and Thermodynamics',
            'Waves and Vibrations',
            'Physical Optics and Gravitational Waves',
            'Electrostatics and Current Electricity',
            'Electromagnetism',
            'Special Theory of Relativity',
            'Nuclear and Particle Physics',
        )),
        'Mathematics': _items(1, (
            'Complex Numbers',
            'Functions and Graphs',
            'Theory of Quadratic Functions',
            'Matrices and Determinants',
            'Partial Fractions',
            'Sequences and Series',
            'Permutations and Combinations',
            'Mathematical Induction and Binomial Theorem',
            'Division of Polynomials',
            'Trigonometric Identities',
            'Trigonometric Functions and their Graphs',
            'Limit and Continuity',
            'Differentiation',
            'Vectors in Space',
        )),
    },
    'item_labels': {'Mathematics': 'Unit'},
    'source_basis': 'Current Punjab / PECTAA Year 11 textbook structure held by the ScoreMax project.',
}


YEAR12 = {
    'label': 'Year 12 · Punjab',
    'collection_label': 'Chapters',
    'subjects': {
        'Biology': _numbered((
            (13, 'Thermoregulation and Osmoregulation'),
            (14, 'Human Urinary System'),
            (15, 'Human Nervous System'),
            (16, 'Human Endocrine System'),
            (17, 'Human Reproductive Systems'),
            (18, 'Inheritance'),
            (19, 'Chromosomes and DNA'),
            (20, 'Biotechnology'),
            (21, 'Immunity'),
            (22, 'Biostatistics'),
            (23, 'Pharmacology'),
            (24, 'Evolution'),
            (25, 'Ecology'),
        )),
        'Chemistry': _numbered((
            (17, 'Group 2 Elements'),
            (18, 'Transition Metals'),
            (19, 'Basics of Organic Chemistry'),
            (20, 'Aromatic Hydrocarbons'),
            (21, 'Halogenoalkanes'),
            (22, 'Hydroxy Compounds'),
            (23, 'Carbonyl Compounds and Carboxylic Acids'),
            (24, 'Organic Nitrogen Compounds'),
            (25, 'Organic Synthesis'),
            (26, 'Polymers'),
            (27, 'Biochemistry'),
            (28, 'Chromatography'),
            (29, 'Spectroscopy–1'),
            (30, 'Spectroscopy-2 NMR'),
            (31, 'Materials and Energy'),
            (32, 'Medicine, Agriculture and Industry'),
            (33, 'Water'),
        )),
        'Physics': _numbered((
            (13, 'Thermal Physics'),
            (14, 'Simple Harmonic Motion'),
            (15, 'Physical Optics'),
            (16, 'Electrostatics'),
            (17, 'Alternating Current'),
            (18, 'Quantum Physics'),
            (19, 'Nuclear and Particle Physics'),
            (20, 'Medical Physics'),
            (21, 'Space and Environment'),
        )),
        'Mathematics': _items(1, (
            'Graphical Representation of Functions',
            'Further Differentiation',
            'Integration',
            'Differential Equations',
            'Analytical Geometry',
            'Conic Section',
            'Kinematics',
            'Numerical Method',
            'Inverse Trigonometric Functions and Their Graphs',
            'Solution of Trigonometric Equations',
            'Vector Valued Functions and Their Differentiations',
        )),
    },
    'item_labels': {'Mathematics': 'Unit'},
    'source_basis': 'Current Punjab / PECTAA Year 12 textbook structure held by the ScoreMax project.',
}


MDCAT = {
    'label': 'MDCAT · PM&DC',
    'collection_label': 'Units',
    'subjects': {
        'Biology': _items(1, (
            'Acellular Life',
            'Bioenergetics',
            'Biological Molecules',
            'Cell Structure & Function',
            'Coordination & Control / Nervous & Chemical Coordination',
            'Enzymes',
            'Evolution',
            'Reproduction',
            'Support & Movement',
            'Inheritance',
            'Circulation',
            'Immunity',
            'Respiration',
            'Digestion',
            'Homeostasis',
            'Biotechnology',
        )),
        'Chemistry': _items(1, (
            'Introduction of Fundamental Concepts of Chemistry',
            'Atomic Structure',
            'Gases',
            'Liquids',
            'Solids',
            'Chemical Equilibrium',
            'Reaction Kinetics',
            'Thermochemistry and Energetics of Chemical Reaction',
            'Electrochemistry',
            'Chemical Bonding',
            'S- and P-Block Elements',
            'Transition Elements',
            'Fundamental Principles of Organic Chemistry',
            'Chemistry of Hydrocarbons',
            'Alkyl Halides',
            'Alcohols and Phenols',
            'Aldehydes and Ketones',
            'Carboxylic Acids',
            'Macromolecules',
            'Industrial Chemistry',
        )),
        'Physics': _items(1, (
            'Vectors and Equilibrium',
            'Force and Motion',
            'Work and Energy',
            'Rotational and Circular Motion',
            'Fluid Dynamics',
            'Waves',
            'Thermodynamics',
            'Electrostatics',
            'Current Electricity',
            'Electromagnetism',
            'Electromagnetic Induction',
            'Alternating Current',
            'Electronics',
            'Dawn of Modern Physics',
            'Atomic Spectra',
            'Nuclear Physics',
        )),
        'English': _items(1, (
            'Reading and Thinking Skills',
            'Formal and Lexical Aspect of Language',
            'Writing Skills',
        )),
        'Logical Reasoning': _numbered((
            ('5.1', 'Critical Thinking'),
            ('5.2', 'Letter and Symbols Series'),
            ('5.3', 'Logical Deductions'),
            ('5.4', 'Logical Problems'),
            ('5.5', 'Course of Action'),
            ('5.6', 'Cause and Effect'),
        )),
    },
    'item_labels': {'English': 'Theme', 'Logical Reasoning': 'Theme'},
    'source_basis': 'Official PM&DC MDCAT curriculum currently held by the ScoreMax project.',
}


CATALOGUES = {'year11': YEAR11, 'year12': YEAR12, 'mdcat': MDCAT}
TRACK_ORDER = ('year11', 'year12', 'mdcat')


def get_catalogue(track: str):
    return CATALOGUES.get((track or '').strip().casefold())


def subject_items(track: str, subject: str):
    catalogue = get_catalogue(track)
    if not catalogue:
        return ()
    return catalogue['subjects'].get(subject, ())
