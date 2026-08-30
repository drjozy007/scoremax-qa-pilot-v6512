# ScoreMax V6.2.2 Browser Acceptance Checklist

Use a copied pilot database and a normal student account.

## Subject flow

- [ ] Open **Learn → Browse Subjects**.
- [ ] Confirm Biology, Chemistry and Physics appear once on the all-subject page.
- [ ] Click Biology.
- [ ] Confirm the next page heading is Biology.
- [ ] Confirm Chemistry and Physics subject cards are not redrawn.
- [ ] Confirm the page says `Choose a Biology chapter`.
- [ ] Confirm only Biology chapters appear.
- [ ] Click `Test Biology` and confirm Biology is preselected.
- [ ] Use `All subjects`, choose Chemistry and repeat the checks.
- [ ] Confirm browser back/forward navigation keeps the correct subject.

## Desktop navigation

- [ ] Confirm the visible student header is Dashboard, Learn, My Plan, Exams, Community and Account.
- [ ] Confirm `Write, Mark & Improve` appears once inside Learn.
- [ ] Confirm Access and Profile & Settings appear only in Account.
- [ ] Confirm all dropdown links open the expected pages.

## Subject quick strip

- [ ] Confirm it does not appear on the Biology or Chemistry detail page.
- [ ] Confirm it remains available where useful, such as chapter and Study Plan pages.
- [ ] Confirm the active subject is highlighted on a chapter page.

## Mobile

- [ ] Confirm the bottom navigation is Home, Learn, Plan, Exams and More.
- [ ] Confirm More opens the mobile menu.
- [ ] Confirm the subject and chapter cards fit without horizontal overflow.

## Regression

- [ ] Login persists over multiple protected requests.
- [ ] Password reset/session-version change still invalidates the old session.
- [ ] Question import, pilot controls and Academic Messages remain accessible to authorised roles.
