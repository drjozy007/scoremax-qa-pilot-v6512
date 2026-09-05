# ScoreMax UX vNext — Canonical Continuity Note

**Date:** 2026-09-05  
**Status:** Active staging redesign; production unchanged.  
**Repository:** `drjozy007/scoremax-qa-pilot-v6512`  
**UX branch:** `feature/v6611c-ux-vnext-landing`  
**Staging service:** `scoremax-ux-vnext-staging`  
**Staging URL:** `https://scoremax-ux-vnext-staging.onrender.com`  
**Production URL:** `https://scoremax.pk`

## 1. Current execution order

The agreed order is:

1. Finish public-site / product UX and branding review on staging.
2. User approves UX.
3. Connect Power House.
4. Import governed questions.
5. Student testing.
6. Teacher testing.

Do **not** move Power House, question import, student testing or teacher testing ahead of UX approval.

## 2. Production safety

- Production `scoremax.pk` remains untouched during UX redesign.
- UX work is staging-only until explicit approval and regression testing.
- Staging reconstructs the qualified V6.6.11C runtime and applies presentation-only overlays.
- Staging uses disposable `/tmp` state and is not a production-data clone.
- No new paid resource should be created without explicit user approval.

## 3. Access / corporate filtering

- `scoremax.pk` opens normally on the user's phone.
- The user's managed laptop blocks `scoremax.pk` because the organisation's web filter categorises it as **Unknown**.
- The staging `onrender.com` URL works on the user's laptop and is therefore the primary UX-review surface.
- Do not change Render / Cloudflare / production configuration to solve the corporate-filter issue.

## 4. Text-editing review mode

A staging-only inline text editor has been added for the homepage:

- `Edit text`
- `Copy changes`
- `Reset`

Text edits are saved only in the browser and are not production writes. The user can copy the change list back into ChatGPT for governed application to the UX branch.

## 5. ScoreMax branding direction

Current brand treatment is **provisional**.

User wants ScoreMax to have much stronger standalone brand identity — comparable in recognisability / confidence to a major brand such as IMAX, without copying IMAX.

Future branding exercise should develop:

- a distinctive ScoreMax wordmark;
- stronger visual emphasis on `MAX`;
- an ownable symbol / app icon / favicon;
- premium, energetic, technology-led identity;
- credible educational tone;
- consistent use across public site, student experience, assessment, teacher areas and future applications.

Do not spend time over-optimising the provisional header mark now; revisit branding deliberately after the main UX structure is stable.

## 6. Public navigation — required logical structure

The user does not want random or overly thin navigation. The intended top-level order is:

**About Us → How It Works → Programmes → Get Involved → Impact → Knowledge Hub → Updates → Help → Login → Start Free**

The exact final spacing / desktop breakpoint can be refined, but the information architecture should remain logical and learner-friendly.

### Get Involved

`Get Involved` should group the engagement / community initiatives:

- Science Genius
- Student Council
- Teacher of the Year

These should not be scattered independently around the homepage.

### Impact

`Impact` should be a separate top-level social-impact pillar, not buried under Get Involved.

It should cover:

- ScoreMax commitment to spend **10% of income** on education / school improvement;
- school-improvement work / projects;
- **Nominate a School** — students and teachers can nominate their school;
- future ability for people to **donate / support education and school improvement**;
- later public impact reporting / transparency.

Important: before production wording, clarify the accounting definition of `10% of income` (e.g. revenue vs profit / another governed basis) so the public claim is precise and auditable.

Donation flow must remain non-transactional until payment, accounting, legal and fund-handling governance are qualified. School nomination can be built earlier.

## 7. Second navigation layer — programmes / exams

Immediately below the top navigation, the user wants a second horizontal programme / exam selector, including at minimum:

- MDCAT
- ECAT
- FSc
- Matric

The structure must be extensible for additional routes later.

The current runtime directly exposes / knows FSc Part 1, FSc Part 2, Grade 9, Grade 10 and MDCAT. ECAT is a desired public route and may need an interest / pre-launch state until its governed product route exists.

Avoid duplicate `Programmes` navigation. The top-level `Programmes` item is the category; the second layer is the actual exam / programme selector.

## 8. Six ScoreMax progression levels

The six boxes are approved visually and should be retained:

1. Foundation
2. Exam Ready
3. Advanced
4. Distinction
5. Expert
6. Elite

User wants these six boxes moved **to the top of the homepage immediately under the second programme / exam layer**, before the main hero / lower landing content.

They should remain prominent and visually strong.

## 9. No dead-end `Coming soon`

`Coming soon` must never be a dead end anywhere on the public site.

Canonical behaviour:

- **Live programme:** `Explore` / `Start practising` / appropriate live CTA.
- **Not-yet-live programme:** `Register interest` / `Join the launch list`.

This rule applies consistently to:

- second-row programme / exam tabs;
- programme cards;
- future programme surfaces.

Interest registration should collect, at minimum:

- programme / exam;
- name;
- email and/or mobile as governed;
- role: student / teacher / parent;
- school / college;
- city / area;
- optional note.

Use the data to notify people when the programme launches and to measure demand by programme / geography / school.

Do not create a second interest system if the canonical runtime already contains one; inspect and reuse / extend existing capability first.

## 10. Public-language governance

Learner-facing / public pages must not expose internal terminology, including examples such as:

- Power House
- Growth Engine
- qualification
- runtime
- release/build identifiers
- firewall / reviewer / QA pipeline internals

Internal terms are acceptable only in properly authenticated admin / internal interfaces.

## 11. Landing-page visual direction

User wants the site to feel **fascinating but user friendly** — modern, intelligent and technology-led, not flashy or cognitively overloaded.

Key direction:

- mobile-first deliberate composition;
- digital / intelligent-learning imagery rather than anatomical brain imagery;
- no oversized black full-screen block;
- stronger hierarchy and less random card accumulation;
- simple learner journey;
- distinctive brand language;
- progression should be immediately visible near the top.

## 12. Header defects already identified

- Original public navigation had random ordering and too many unrelated links.
- Brand and first navigation item overlapped at some desktop widths.
- Header should switch to hamburger before links collide.
- A provisional brand lockup / collision fix is already on the UX branch.

## 13. Staging implementation status as of this note

The latest confirmed successful staging deploy before this note is commit:

`8a9acc1b300c65c779326b9d7e8c05bfacf712ce`

Render deploy:

`dep-dae30ov40ujc73djg6tg` — **LIVE**

This deployment contains the hardened materializer and provisional ScoreMax brand lockup.

A later staging-only CSS file for the layered public information architecture has been created:

`ux_vnext_overlay/static/ux_structure_v2.css`

Commit:

`ffe2f5a8a282f2b594ef4c0788b488397dfcfdd4`

That later structure work should be treated as **in progress / not yet confirmed deployed** at the time of this continuity note. Do not assume the second-row programme rail, Impact cards, Get Involved structure or interest form are already live until a successful Render deploy and visual verification are completed.

## 14. Immediate next implementation task

Continue the UX branch by integrating and deploying the agreed structure in one coherent pass:

1. logical top navigation with About Us first;
2. Get Involved dropdown / area for Science Genius, Student Council, Teacher of the Year;
3. separate Impact top-level item;
4. second-row MDCAT / ECAT / FSc / Matric programme selector;
5. six progression boxes directly below that row;
6. live vs Register-interest behaviour with no dead-end `Coming soon`;
7. real staging interest-registration workflow, reusing canonical capability if it already exists;
8. school nomination / 10% Impact presentation on staging, with donations non-transactional;
9. desktop + mobile visual regression and overlap check;
10. user reviews staging again.

Production remains unchanged until explicit UX approval.
