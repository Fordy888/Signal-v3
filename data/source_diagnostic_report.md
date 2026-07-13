# Signal Source Diagnostic Report

**Date:** 2026-07-13 00:14 UTC
**Environment:** Sandbox (not Render)

## Summary

| Metric | Count |
|--------|-------|
| Total tested | 95 |
| Succeeded | 81 |
| Failed | 10 |
| Parse errors | 2 |
| Empty feeds | 2 |
| Disabled (skipped) | 13 |

## Error Breakdown

| Error Type | Count | Example Sources |
|-----------|-------|-----------------|
| http_404 | 7 | Anthropic News, The Rundown AI, Deloitte Insights |
| parse_error | 2 | Harvard Business Review — AI, Google Cloud Blog |
| empty_feed | 2 | Parliament — Joint Committee Inquiries, Parliament — House Inquiries |
| http_403 | 1 | Axios AI+ |
| http_410 | 1 | Microsoft AI Blog |
| http_400 | 1 | Meta AI Blog |

## Failed Sources (Full List)

| # | Name | Domain | Category | Error | Recommendation |
|---|------|--------|----------|-------|----------------|
| 1 | Parliament — Joint Committee Inquiries | www.aph.gov.au | australian_government_policy | empty_feed | check_if_feed_moved |
| 2 | Parliament — House Inquiries | www.aph.gov.au | australian_government_policy | empty_feed | check_if_feed_moved |
| 3 | Meta AI Blog | ai.meta.com | ai_market_signals | http_400 | investigate_manually |
| 4 | Axios AI+ | www.axios.com | ai_market_signals | http_403 | blocked_needs_different_approach_or_disable |
| 5 | Anthropic News | www.anthropic.com | ai_market_signals | http_404 | find_new_feed_url |
| 6 | The Rundown AI | www.therundown.ai | ai_market_signals | http_404 | find_new_feed_url |
| 7 | Deloitte Insights | www2.deloitte.com | strategy_decision_making | http_404 | find_new_feed_url |
| 8 | Bain & Company Insights | www.bain.com | strategy_decision_making | http_404 | find_new_feed_url |
| 9 | a16z (Andreessen Horowitz) | a16z.com | venture_capital | http_404 | find_new_feed_url |
| 10 | TLDR AI | tldr.tech | tactical_ai_stack | http_404 | find_new_feed_url |
| 11 | Superhuman AI (Zain Kahn) | www.superhuman.ai | tactical_ai_stack | http_404 | find_new_feed_url |
| 12 | Microsoft AI Blog | blogs.microsoft.com | ai_market_signals | http_410 | disable_permanently_gone |
| 13 | Harvard Business Review — AI | hbr.org | strategy_decision_making | parse_error | investigate_feed_format |
| 14 | Google Cloud Blog | cloud.google.com | ai_market_signals | parse_error | investigate_feed_format |

## Successful Sources

| # | Name | Domain | Category | Items | UA Used |
|---|------|--------|----------|-------|---------|
| 1 | OpenAI Blog | openai.com | ai_market_signals | 1040 | browser_chrome |
| 2 | Google DeepMind Blog | deepmind.google | ai_market_signals | 100 | browser_chrome |
| 3 | Google AI Blog | blog.google | ai_market_signals | 20 | browser_chrome |
| 4 | Hugging Face Blog | huggingface.co | ai_market_signals | 823 | browser_chrome |
| 5 | Simon Willison | simonwillison.net | ai_market_signals | 30 | browser_chrome |
| 6 | Import AI (Jack Clark) | importai.substack.com | ai_market_signals | 20 | browser_chrome |
| 7 | The Gradient | thegradient.pub | ai_market_signals | 15 | browser_chrome |
| 8 | MIT Technology Review — AI | www.technologyreview.com | ai_market_signals | 10 | browser_chrome |
| 9 | Wired — AI | www.wired.com | ai_market_signals | 10 | browser_chrome |
| 10 | Ars Technica — Technology | feeds.arstechnica.com | ai_market_signals | 20 | browser_chrome |
| 11 | TechCrunch — AI | techcrunch.com | ai_market_signals | 20 | browser_chrome |
| 12 | Platformer (Casey Newton) | www.platformer.news | ai_market_signals | 15 | browser_chrome |
| 13 | Financial Times — Artificial Intelligence | www.ft.com | ai_market_signals | 25 | browser_chrome |
| 14 | The Information | www.theinformation.com | ai_market_signals | 20 | browser_chrome |
| 15 | One Useful Thing (Ethan Mollick) | www.oneusefulthing.org | ai_market_signals | 20 | browser_chrome |
| 16 | Interconnects (Nathan Lambert) | www.interconnects.ai | ai_market_signals | 20 | browser_chrome |
| 17 | The Economist — Science & Technology | www.economist.com | ai_market_signals | 300 | browser_chrome |
| 18 | AI For Leaders (Adam Danyal) | aiforleaders.substack.com | ai_market_signals | 6 | browser_chrome |
| 19 | Apple Machine Learning Research | machinelearning.apple.com | ai_market_signals | 10 | browser_chrome |
| 20 | Nvidia AI Blog | blogs.nvidia.com | ai_market_signals | 18 | browser_chrome |
| 21 | Stratechery (Ben Thompson) | stratechery.com | strategy_decision_making | 10 | browser_chrome |
| 22 | McKinsey Insights | www.mckinsey.com | strategy_decision_making | 50 | browser_chrome |
| 23 | Farnam Street Blog | fs.blog | strategy_decision_making | 20 | browser_chrome |
| 24 | Cedric Chin (Commoncog) | commoncog.com | strategy_decision_making | 15 | browser_chrome |
| 25 | Paul Graham Essays | www.aaronsw.com | strategy_decision_making | 219 | browser_chrome |
| 26 | Benedict Evans | www.ben-evans.com | strategy_decision_making | 20 | browser_chrome |
| 27 | Bits About Money (Patrick McKenzie) | www.bitsaboutmoney.com | strategy_decision_making | 15 | browser_chrome |
| 28 | Sequoia Capital | www.sequoiacap.com | venture_capital | 10 | browser_chrome |
| 29 | Y Combinator Blog | www.ycombinator.com | venture_capital | 15 | browser_chrome |
| 30 | CB Insights Research | www.cbinsights.com | venture_capital | 25 | browser_chrome |
| 31 | Fred Wilson (AVC) | avc.com | venture_capital | 10 | browser_chrome |
| 32 | Matt Levine (Bloomberg) | www.bloomberg.com | venture_capital | 20 | browser_chrome |
| 33 | Aswath Damodaran | aswathdamodaran.blogspot.com | venture_capital | 25 | browser_chrome |
| 34 | VentureBeat | venturebeat.com | venture_capital | 7 | browser_chrome |
| 35 | How I Built This (NPR) | feeds.npr.org | opportunity_radar | 849 | browser_chrome |
| 36 | SaaStr Blog | www.saastr.com | opportunity_radar | 10 | browser_chrome |
| 37 | Intercom Blog | www.intercom.com | opportunity_radar | 10 | browser_chrome |
| 38 | Tim Ferriss Blog | tim.blog | opportunity_radar | 10 | browser_chrome |
| 39 | Daring Fireball (John Gruber) | daringfireball.net | opportunity_radar | 48 | browser_chrome |
| 40 | Latent Space (AI Engineering) | www.latent.space | opportunity_radar | 20 | browser_chrome |
| 41 | Lenny's Newsletter | www.lennysnewsletter.com | opportunity_radar | 20 | browser_chrome |
| 42 | Foreign Affairs | www.foreignaffairs.com | geopolitics | 20 | browser_chrome |
| 43 | The Economist — Leaders | www.economist.com | geopolitics | 300 | browser_chrome |
| 44 | War on the Rocks | warontherocks.com | geopolitics | 100 | browser_chrome |
| 45 | ASPI — The Strategist | www.aspistrategist.org.au | geopolitics | 100 | browser_chrome |
| 46 | Lowy Institute — The Interpreter | www.lowyinstitute.org | geopolitics | 50 | browser_chrome |
| 47 | Rest of World | restofworld.org | geopolitics | 12 | old_signal_ua |
| 48 | Chartbook (Adam Tooze) | adamtooze.substack.com | geopolitics | 20 | browser_chrome |
| 49 | Politico — Technology | rss.politico.com | geopolitics | 30 | browser_chrome |
| 50 | SmartCompany | www.smartcompany.com.au | australian_business | 10 | browser_chrome |
| 51 | StartupDaily | www.startupdaily.net | australian_business | 10 | browser_chrome |
| 52 | Dynamic Business | dynamicbusiness.com | australian_business | 20 | browser_chrome |
| 53 | ABC News — Business | www.abc.net.au | australian_business | 25 | browser_chrome |
| 54 | The Conversation AU — Business | theconversation.com | australian_business | 25 | browser_chrome |
| 55 | Guardian Australia — Business | www.theguardian.com | australian_business | 28 | browser_chrome |
| 56 | Crikey | www.crikey.com.au | australian_business | 10 | browser_chrome |
| 57 | Sifted (EU tech) | sifted.eu | australian_business | 24 | browser_chrome |
| 58 | RBA — Media Releases | www.rba.gov.au | australian_government_policy | 1 | old_signal_ua |
| 59 | RBA — Speeches | www.rba.gov.au | australian_government_policy | 1 | old_signal_ua |
| 60 | APRA — Prudential Regulation Authority | www.apra.gov.au | australian_government_policy | 10 | browser_chrome |
| 61 | Parliament — Senate New Inquiries | www.aph.gov.au | australian_government_policy | 33 | browser_chrome |
| 62 | Parliament — Senate Reports Tabled | www.aph.gov.au | australian_government_policy | 96 | browser_chrome |
| 63 | The Mandarin | www.themandarin.com.au | australian_government_policy | 10 | browser_chrome |
| 64 | Tech Council of Australia | techcouncil.com.au | australian_government_policy | 10 | browser_chrome |
| 65 | Government News | www.governmentnews.com.au | australian_government_policy | 14 | browser_chrome |
| 66 | The Conversation AU — Politics & Policy | theconversation.com | australian_government_policy | 25 | browser_chrome |
| 67 | ControlAI | controlai.substack.com | threat_detection | 4 | browser_chrome |
| 68 | Zvi Mowshowitz (Don't Worry About the Vase) | thezvi.substack.com | ai_market_signals | 20 | browser_chrome |
| 69 | AI Snake Oil (Arvind Narayanan) | www.aisnakeoil.com | threat_detection | 20 | browser_chrome |
| 70 | Kottke.org | feeds.kottke.org | cultural_economic_shifts | 60 | browser_chrome |
| 71 | The Atlantic — Ideas | www.theatlantic.com | cultural_economic_shifts | 25 | browser_chrome |
| 72 | Marginal Revolution | marginalrevolution.com | cultural_economic_shifts | 15 | browser_chrome |
| 73 | Wait But Why | waitbutwhy.com | cultural_economic_shifts | 10 | browser_chrome |
| 74 | Palladium Magazine | www.palladiummag.com | cultural_economic_shifts | 18 | browser_chrome |
| 75 | Quartz | qz.com | cultural_economic_shifts | 11 | browser_chrome |
| 76 | Wired — Business | www.wired.com | cultural_economic_shifts | 20 | browser_chrome |
| 77 | Product Hunt | www.producthunt.com | tactical_ai_stack | 50 | browser_chrome |
| 78 | Ben's Bites | www.bensbites.com | tactical_ai_stack | 20 | browser_chrome |
| 79 | AWS Enterprise Strategy Blog | aws.amazon.com | strategy_decision_making | 20 | browser_chrome |
| 80 | CIO Dive | www.ciodive.com | strategy_decision_making | 10 | browser_chrome |
| 81 | HackerNews | hacker-news.firebaseio.com | ai_market_signals | 5 | unknown |

## Category Coverage (Successful Sources Only)

| Category | Items Available |
|----------|---------------|
| ai_market_signals | 2567 |
| opportunity_radar | 967 |
| geopolitics | 632 |
| strategy_decision_making | 379 |
| australian_government_policy | 200 |
| cultural_economic_shifts | 159 |
| australian_business | 152 |
| venture_capital | 112 |
| tactical_ai_stack | 70 |
| threat_detection | 24 |

## Recommendations

### Find New Feed Url (7 sources)
- Anthropic News
- The Rundown AI
- Deloitte Insights
- Bain & Company Insights
- a16z (Andreessen Horowitz)
- TLDR AI
- Superhuman AI (Zain Kahn)

### Investigate Feed Format (2 sources)
- Harvard Business Review — AI
- Google Cloud Blog

### Check If Feed Moved (2 sources)
- Parliament — Joint Committee Inquiries
- Parliament — House Inquiries

### Blocked Needs Different Approach Or Disable (1 sources)
- Axios AI+

### Disable Permanently Gone (1 sources)
- Microsoft AI Blog

### Investigate Manually (1 sources)
- Meta AI Blog
