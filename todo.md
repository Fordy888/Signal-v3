# DTL Signal Incident TODO

- [x] Diagnose Edition 0038 subject/body date-alignment QA failure
- [x] Confirm which production commit and configuration ran on 24 August 2026
- [x] Inspect generated Edition 0038 metadata behaviour and production logs
- [x] Implement the smallest root-cause fix
- [x] Add regression tests for correct, incorrect, and missing edition date metadata
- [ ] Run a proof of the corrected Edition 0038 to paul.ford@gmail.com
- [ ] Verify subject, body date, content mix, formatting, QA and delivery
- [ ] Decide whether to recover/send today’s held edition
- [ ] Record the incident cause and resolution
- [x] Fix dry-run recipient display when firstName is null
- [ ] Exclude the known test and bounced addresses still present in the live subscriber API before recovery send
