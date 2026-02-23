"""
Labeled evaluation dataset for NLP classifier accuracy measurement.

120+ sentences across 4 label categories (fact, opinion, mixed, unclear)
and 3 difficulty categories (easy, hard, edge_case).

Sentences are written in typical news prose style (BBC, Reuters, AP)
without copying from copyrighted articles.
"""

EVAL_SENTENCES: list[dict] = [
    # =========================================================================
    # FACTUAL SENTENCES — 30 clear facts (statistics, dates, named events, measurements)
    # =========================================================================
    {"text": "The unemployment rate fell to 3.7 percent in November, the Bureau of Labor Statistics reported.", "expected_label": "fact", "category": "easy"},
    {"text": "Global carbon dioxide emissions reached 36.8 billion tonnes in 2023, a new record.", "expected_label": "fact", "category": "easy"},
    {"text": "The earthquake measured 6.4 on the Richter scale and struck at 4:17 a.m. local time.", "expected_label": "fact", "category": "easy"},
    {"text": "Voter turnout in the general election was 67.3 percent, the highest since 1992.", "expected_label": "fact", "category": "easy"},
    {"text": "The European Central Bank raised interest rates by 25 basis points on Thursday.", "expected_label": "fact", "category": "easy"},
    {"text": "NASA's Artemis III mission is scheduled to launch in September 2026.", "expected_label": "fact", "category": "easy"},
    {"text": "The population of Tokyo's metropolitan area is approximately 37 million people.", "expected_label": "fact", "category": "easy"},
    {"text": "The Dow Jones Industrial Average closed at 38,654 points, up 1.2 percent on the day.", "expected_label": "fact", "category": "easy"},
    {"text": "Average global temperatures in 2024 were 1.45 degrees Celsius above pre-industrial levels.", "expected_label": "fact", "category": "easy"},
    {"text": "The company reported quarterly revenue of 14.2 billion dollars, up 8 percent year over year.", "expected_label": "fact", "category": "easy"},
    {"text": "Inflation in the eurozone fell to 2.4 percent in March, according to preliminary data from Eurostat.", "expected_label": "fact", "category": "easy"},
    {"text": "The bridge spans 1,280 metres and was completed in 18 months at a cost of 3.4 billion dollars.", "expected_label": "fact", "category": "easy"},
    {"text": "Russia's central bank held its key interest rate at 16 percent at its Friday meeting.", "expected_label": "fact", "category": "easy"},
    {"text": "The spacecraft travelled 225 million kilometres before entering Mars orbit.", "expected_label": "fact", "category": "easy"},
    {"text": "Three people were killed and seventeen injured in the train derailment near Lyon.", "expected_label": "fact", "category": "easy"},
    {"text": "South Korea's GDP grew 2.6 percent in 2024, slightly above government forecasts.", "expected_label": "fact", "category": "easy"},
    {"text": "The pharmaceutical company enrolled 12,400 participants in the phase three clinical trial.", "expected_label": "fact", "category": "easy"},
    {"text": "Water levels in the Rhine dropped to 78 centimetres at the Kaub gauge on Tuesday.", "expected_label": "fact", "category": "easy"},
    {"text": "The country's national debt stood at 33.1 trillion dollars at the end of the fiscal year.", "expected_label": "fact", "category": "easy"},
    {"text": "The election was held on 4 November and produced a coalition government of three parties.", "expected_label": "fact", "category": "easy"},
    {"text": "The suspect was arrested at 2:15 a.m. in the 1200 block of North Avenue.", "expected_label": "fact", "category": "easy"},
    {"text": "Total rainfall in the region exceeded 340 millimetres during the 72-hour period.", "expected_label": "fact", "category": "easy"},
    {"text": "The World Health Organization confirmed 2,847 new cases in the affected provinces.", "expected_label": "fact", "category": "easy"},
    {"text": "Construction began in April 2022 and the facility is expected to employ 800 workers.", "expected_label": "fact", "category": "easy"},
    {"text": "The aircraft was carrying 189 passengers and crew when it made the emergency landing.", "expected_label": "fact", "category": "easy"},
    {"text": "Sweden joined NATO on 7 March 2024, becoming the alliance's 32nd member.", "expected_label": "fact", "category": "easy"},
    {"text": "The lithium deposit contains an estimated 400,000 tonnes of extractable ore.", "expected_label": "fact", "category": "easy"},
    {"text": "Average house prices in London fell 1.9 percent in the first quarter.", "expected_label": "fact", "category": "easy"},
    {"text": "The solar farm covers 800 hectares and generates 550 megawatts of electricity.", "expected_label": "fact", "category": "easy"},
    {"text": "Parliament passed the bill with 312 votes in favour and 247 against.", "expected_label": "fact", "category": "easy"},

    # =========================================================================
    # OPINION SENTENCES — 30 clear opinions (judgments, should/must, predictions, editorializing)
    # =========================================================================
    {"text": "The government's handling of the crisis has been nothing short of disastrous.", "expected_label": "opinion", "category": "easy"},
    {"text": "Policymakers should prioritise renewable energy investment over fossil fuel subsidies.", "expected_label": "opinion", "category": "easy"},
    {"text": "The proposed tax reform is the most significant step forward in fiscal policy in decades.", "expected_label": "opinion", "category": "easy"},
    {"text": "It would be a grave mistake to withdraw peacekeeping forces from the region at this stage.", "expected_label": "opinion", "category": "easy"},
    {"text": "The president's speech was a masterclass in political rhetoric but offered little of substance.", "expected_label": "opinion", "category": "easy"},
    {"text": "Congress must act immediately to address the growing homelessness epidemic.", "expected_label": "opinion", "category": "easy"},
    {"text": "The new regulations will almost certainly stifle innovation in the technology sector.", "expected_label": "opinion", "category": "easy"},
    {"text": "This deal represents the worst value for taxpayers in the history of public procurement.", "expected_label": "opinion", "category": "easy"},
    {"text": "Voters deserve better than the cynical posturing that has defined this election campaign.", "expected_label": "opinion", "category": "easy"},
    {"text": "The education system is failing an entire generation of young people.", "expected_label": "opinion", "category": "easy"},
    {"text": "It is imperative that the international community holds the regime accountable for its actions.", "expected_label": "opinion", "category": "easy"},
    {"text": "The prime minister's resignation was long overdue and should have come months ago.", "expected_label": "opinion", "category": "easy"},
    {"text": "Artificial intelligence poses an existential threat that humanity is woefully unprepared to confront.", "expected_label": "opinion", "category": "easy"},
    {"text": "The central bank's decision to pause rate hikes was reckless and irresponsible.", "expected_label": "opinion", "category": "easy"},
    {"text": "This trade agreement will ultimately benefit wealthy corporations at the expense of ordinary workers.", "expected_label": "opinion", "category": "easy"},
    {"text": "The court's ruling sets a dangerous precedent that will erode civil liberties for years to come.", "expected_label": "opinion", "category": "easy"},
    {"text": "Healthcare reform is the defining moral challenge of our time.", "expected_label": "opinion", "category": "easy"},
    {"text": "The mayor's infrastructure plan is ambitious but deeply unrealistic given current budget constraints.", "expected_label": "opinion", "category": "easy"},
    {"text": "Social media companies should be held legally responsible for harmful content on their platforms.", "expected_label": "opinion", "category": "easy"},
    {"text": "The defence budget is bloated and should be redirected to education and public health.", "expected_label": "opinion", "category": "easy"},
    {"text": "Deregulation of the banking sector would be a catastrophic repeat of the mistakes that caused the 2008 crisis.", "expected_label": "opinion", "category": "easy"},
    {"text": "The diplomatic approach has clearly failed and stronger measures are now necessary.", "expected_label": "opinion", "category": "easy"},
    {"text": "This is the best opportunity in a generation to reform the immigration system.", "expected_label": "opinion", "category": "easy"},
    {"text": "The opposition's economic plan lacks credibility and would plunge the country deeper into debt.", "expected_label": "opinion", "category": "easy"},
    {"text": "We cannot afford to ignore the scientific consensus on climate change any longer.", "expected_label": "opinion", "category": "easy"},
    {"text": "The merger would create an unacceptable concentration of market power in the telecommunications industry.", "expected_label": "opinion", "category": "easy"},
    {"text": "Prison reform is urgently needed to address the cycle of reoffending.", "expected_label": "opinion", "category": "easy"},
    {"text": "The tech industry's self-regulation has been a spectacular failure.", "expected_label": "opinion", "category": "easy"},
    {"text": "Investing in early childhood education yields the highest returns of any public spending.", "expected_label": "opinion", "category": "easy"},
    {"text": "The proposed highway expansion is an outdated solution to a modern transportation problem.", "expected_label": "opinion", "category": "easy"},

    # =========================================================================
    # ATTRIBUTED SPEECH — 20 sentences with attribution patterns (expected: mixed)
    # =========================================================================
    {"text": "The minister said the new policy would create 50,000 jobs within two years.", "expected_label": "mixed", "category": "easy"},
    {"text": "According to the chief economist, inflation will remain above target through the end of the year.", "expected_label": "mixed", "category": "easy"},
    {"text": "Officials claimed the weapons programme had been dismantled in compliance with the agreement.", "expected_label": "mixed", "category": "easy"},
    {"text": "The CEO told reporters that the company planned to cut its workforce by 15 percent.", "expected_label": "mixed", "category": "easy"},
    {"text": "Sources said the negotiations had stalled over disagreements about territorial boundaries.", "expected_label": "mixed", "category": "easy"},
    {"text": "The spokesperson announced that the product recall would affect 2.3 million units.", "expected_label": "mixed", "category": "easy"},
    {"text": "The general warned that further escalation could destabilise the entire region.", "expected_label": "mixed", "category": "easy"},
    {"text": "In a statement, the bank confirmed it was under investigation for money laundering.", "expected_label": "mixed", "category": "easy"},
    {"text": "The ambassador argued that sanctions were counterproductive and harmed ordinary citizens.", "expected_label": "mixed", "category": "easy"},
    {"text": "Experts suggest that the variant may be more transmissible but less severe.", "expected_label": "mixed", "category": "easy"},
    {"text": "The union leader declared that members would strike unless management met their demands.", "expected_label": "mixed", "category": "easy"},
    {"text": "Researchers reported that the drug reduced symptoms by 42 percent in clinical trials.", "expected_label": "mixed", "category": "easy"},
    {"text": "The prime minister insisted that the government had no prior knowledge of the incident.", "expected_label": "mixed", "category": "easy"},
    {"text": "According to intelligence officials, the cyber attack originated from a state-sponsored group.", "expected_label": "mixed", "category": "easy"},
    {"text": "The director explained that budget cuts would force the closure of three regional offices.", "expected_label": "mixed", "category": "easy"},
    {"text": "A spokesperson said the airline would compensate affected passengers within 14 business days.", "expected_label": "mixed", "category": "easy"},
    {"text": "The president denied allegations that the administration had mishandled classified documents.", "expected_label": "mixed", "category": "easy"},
    {"text": "Scientists indicated that the ice sheet was losing mass at an accelerating rate.", "expected_label": "mixed", "category": "easy"},
    {"text": "The mayor noted that crime rates had dropped for the third consecutive quarter.", "expected_label": "mixed", "category": "easy"},
    {"text": "Officials say the death toll from the flooding has risen to at least 45.", "expected_label": "mixed", "category": "easy"},

    # =========================================================================
    # UNCLEAR — 15 short/ambiguous sentences (under 30 tokens, headlines, fragments)
    # =========================================================================
    {"text": "Markets rally on rate hopes.", "expected_label": "unclear", "category": "easy"},
    {"text": "More details to follow.", "expected_label": "unclear", "category": "easy"},
    {"text": "Developing story.", "expected_label": "unclear", "category": "easy"},
    {"text": "Updated at 3:15 p.m.", "expected_label": "unclear", "category": "easy"},
    {"text": "Breaking: Explosion reported near embassy.", "expected_label": "unclear", "category": "easy"},
    {"text": "Talks continue.", "expected_label": "unclear", "category": "easy"},
    {"text": "See related coverage below.", "expected_label": "unclear", "category": "easy"},
    {"text": "Live updates.", "expected_label": "unclear", "category": "easy"},
    {"text": "Photo credit: Reuters.", "expected_label": "unclear", "category": "easy"},
    {"text": "With additional reporting from the Associated Press.", "expected_label": "unclear", "category": "easy"},
    {"text": "Read the full report here.", "expected_label": "unclear", "category": "easy"},
    {"text": "What happens next?", "expected_label": "unclear", "category": "easy"},
    {"text": "Story developing.", "expected_label": "unclear", "category": "easy"},
    {"text": "Correction appended.", "expected_label": "unclear", "category": "easy"},
    {"text": "Editor's note.", "expected_label": "unclear", "category": "easy"},

    # =========================================================================
    # HARD CASES — 15 sentences with hedging, implied opinion, embedded judgment
    # =========================================================================
    {"text": "Critics point out that the 3 percent growth figure masks widening inequality across income groups.", "expected_label": "opinion", "category": "hard"},
    {"text": "The surprisingly strong jobs report suggests the economy may be more resilient than previously thought.", "expected_label": "opinion", "category": "hard"},
    {"text": "Despite government assurances, many analysts remain deeply sceptical of the recovery projections.", "expected_label": "opinion", "category": "hard"},
    {"text": "Some economists question whether the current deficit spending is sustainable in the long term.", "expected_label": "opinion", "category": "hard"},
    {"text": "The data paints a troubling picture of declining educational outcomes in rural areas.", "expected_label": "opinion", "category": "hard"},
    {"text": "While technically legal, the tax arrangement has drawn criticism from transparency campaigners.", "expected_label": "fact", "category": "hard"},
    {"text": "The policy has failed to deliver on its central promise of reducing waiting times.", "expected_label": "opinion", "category": "hard"},
    {"text": "Preliminary results indicate a statistically significant improvement, though the sample size was small.", "expected_label": "fact", "category": "hard"},
    {"text": "The company's environmental record stands in stark contrast to its green marketing campaigns.", "expected_label": "opinion", "category": "hard"},
    {"text": "Whether the ceasefire will hold remains an open question given the history of broken agreements.", "expected_label": "opinion", "category": "hard"},
    {"text": "Proponents of the legislation argue it will create a level playing field, but opponents warn it will kill small businesses.", "expected_label": "fact", "category": "hard"},
    {"text": "The audit revealed irregularities in 14 percent of the contracts reviewed.", "expected_label": "fact", "category": "hard"},
    {"text": "Rising sea levels threaten to displace millions of coastal residents by mid-century, according to projections.", "expected_label": "fact", "category": "hard"},
    {"text": "The so-called reform package amounts to little more than cosmetic changes to a broken system.", "expected_label": "opinion", "category": "hard"},
    {"text": "At 14 percent, youth unemployment remains stubbornly high despite repeated government interventions.", "expected_label": "fact", "category": "hard"},

    # =========================================================================
    # EDGE CASES — 10 sentences (satire, breaking news stubs, single-word, rhetorical)
    # =========================================================================
    {"text": "Area man confident he could manage national economy better than Federal Reserve chair.", "expected_label": "unclear", "category": "edge_case"},
    {"text": "Nation somehow surprised by completely predictable infrastructure collapse.", "expected_label": "unclear", "category": "edge_case"},
    {"text": "Breaking: Major earthquake strikes coastal city.", "expected_label": "unclear", "category": "edge_case"},
    {"text": "Just in: Presidential motorcade diverted amid security concerns.", "expected_label": "unclear", "category": "edge_case"},
    {"text": "Indeed.", "expected_label": "unclear", "category": "edge_case"},
    {"text": "Yes.", "expected_label": "unclear", "category": "edge_case"},
    {"text": "Is this really the best we can do as a society?", "expected_label": "unclear", "category": "edge_case"},
    {"text": "Meanwhile, in other news that will shock absolutely no one.", "expected_label": "unclear", "category": "edge_case"},
    {"text": "Developing story: Authorities respond to reports of active situation downtown.", "expected_label": "unclear", "category": "edge_case"},
    {"text": "Well.", "expected_label": "unclear", "category": "edge_case"},
]
