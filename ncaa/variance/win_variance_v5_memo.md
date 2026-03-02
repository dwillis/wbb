# Does Maryland Actually Win Different Ways, or Does It Just Feel That Way?

### After adjusting for opponents, the Terps' apparent variety drops from 5th in the country to 30th. But the truth is more interesting than the ranking.

---

I've had season tickets at Maryland for a while now, and this year I kept noticing something: the Terps didn't seem to win the same way twice. Some nights they crashed the offensive glass. Other nights the defense forced a pile of turnovers. Occasionally they just shot well and got out of the way. It felt like a team with multiple identities, which seemed like a good thing heading into March.

So I tried to measure it. The question isn't "how good is Maryland?" — there are plenty of ways to answer that. It's "how many different ways can they win?"

## The setup

Using box score data from every D-I game this season, I computed nine stats for each game that capture playing style: shooting efficiency, turnover rate, offensive rebounding, three-point volume, and their defensive equivalents. Then I grouped all winning games across the 77 teams with 20+ wins into five broad "archetypes" — five distinct patterns of how a game gets won. Think of them as: *won by rebounding*, *won by forcing turnovers*, *won by shooting volume*, and so on.

A team whose wins are spread evenly across all five archetypes is highly versatile. A team whose wins all land in one bucket is doing the same thing every night.

## The opponent problem

Here's where things get tricky. Maryland plays in the Big Ten, which means their schedule includes USC, Ohio State, and UCLA alongside Minnesota and Rutgers. Playing opponents of wildly different quality naturally produces wildly different stat lines — even if a team doesn't change its approach at all.

To deal with this, I adjusted every game stat against the opponent's season averages. If Maryland shoots .520 against a team that typically allows .490, that's a +.030 residual — they shot better than expected. If they shoot .480 against a team allowing .470, that's only +.010. The residuals strip out the schedule and isolate what a team *actually changed*.

This adjustment reshuffles the rankings dramatically. The correlation between raw and adjusted rankings is just 0.52 — meaning about half the apparent variety in the country was really just schedule noise.

## What happened to Maryland

Before opponent adjustment, Maryland ranked **5th** nationally in win versatility. That matches the eye test perfectly. After adjusting? They drop to **30th**.

That sounds bad, but it's not the whole story. Maryland's wins still split across three distinct archetypes, with no single pattern dominating: 34% of their wins came via above-average forced turnovers, 32% through offensive rebounding, and 27% by winning without relying on the three-point line. The gap between their top two patterns is almost nothing — a ratio of just 1.09. That three-way split is real variety, even if the magnitude got inflated by the Big Ten schedule.

They aren't alone in this. Ohio State drops 37 spots after adjustment. West Virginia falls 46. Vanderbilt, playing SEC opponents of varying quality, drops 48. The schedule effect is powerful and it runs in both directions: Alabama *climbs* 45 spots because their variety was genuine, not a schedule artifact. St. John's rises 49 spots — their Big East opponents masked real tactical adaptation. South Carolina, often assumed to play the same way every night, climbs 37 spots once you control for opponents.

## The extremes

At the top, **Michigan State** is the most versatile team in the country, with wins spread almost perfectly across all five archetypes. North Carolina is close behind. At the bottom, **Texas** is a remarkable outlier: 26 wins, and 98% of them fall into a single archetype. They have found one way to win and they run it every night. That's not a criticism — 26 wins is 26 wins — but it's the statistical opposite of variety.

## What this means for March

Versatility isn't the same as quality. Texas may be predictable and very good. Michigan State may be unpredictable and lose in the second round. But if you're a Maryland fan wondering whether this team can adapt when a game plan falls apart, the numbers say: yes, with a caveat. The Terps genuinely win in multiple ways, which should make them harder to scout. They just don't do it quite as often as the raw box scores suggest.

---

### Recommended plots and suggested improvements

**Use these three:**

- **Plot 08 (raw vs. residual scatter)** — This is the centerpiece. It shows every team's raw versatility ranking vs. their opponent-adjusted ranking, with the biggest movers labeled. Readers immediately see who was inflated by schedule and who was hidden by it.
  - *Better title:* "How Much of That Variety Was Just the Schedule?"
  - *Better subtitle:* "Teams above the diagonal line are more versatile than raw stats suggest; teams below were flattered by opponent differences"

- **Plot 03 (archetype composition bars)** — Shows the top-25 teams' win distribution across archetypes as stacked bars. Maryland's three-way split is immediately visible, and Texas's single-archetype dominance is striking.
  - *Better title:* "Five Ways to Win, and Who Uses Which"
  - *Better subtitle:* "Share of each team's wins assigned to each archetype, weighted by game closeness"

- **Plot 01 (entropy ranking)** — The basic "most to least versatile" bar chart. Good as a reference for readers who want to find their team.
  - *Better title:* "The Versatility Ladder"
  - *Better subtitle:* "Opponent-adjusted win variety for the 77 teams with 20+ wins, 2025-26"

**Skip these for a general audience:** Plots 02 (archetype centroid profiles), 04 (HHI vs entropy), 06 (sensitivity heatmap), and 07 (ICC weights) are useful diagnostics but too technical for a newsletter format. Plot 05 (versatility composite) largely duplicates Plot 01.
