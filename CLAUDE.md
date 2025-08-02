## Summary

The purpose of this Python app is to conduct analysis of various sports books and prediction markets to evaluate how accurate each platform is, relative to reality. This will require creating a database storing the odds for each platform at various points in time before each event (match) start time, as well as storing the final outcome of each match in reality. This will require a standardized table of games (or matches) to which each platform's markets and odds data are linked.

## Scope

- We'll analyze Polymarket, Kalshi, and sportsbooks. (We'll possibly add PredictIt later on.) Wherever possible for those named platforms, we will use official APIs (although for the sportsbooks, just use The Odds API, which collects odds for many sportsbooks).
- Use the Polymarket API to create game entities in the first place. Be sure to use the Gamma API's 'events' endpoint (see https://docs.polymarket.com/developers/gamma-markets-api/get-events) to get the actual list of MLB games (with their nested markets) and filter for 'tag_id' of '100381' (for MLB). Use the team names in the event 'title' field and the game's start date/time in the 'gameStartTime' field within each event's 'markets' list to create or find the official game entity in a table. After creating/finding the game, then proceed to collect the odds data at this point in time.
- The Kalshi API's 'markets' endpoint doesn't actually have a field that explicitly lists the game start times. So you'll need to use fields like 'title', 'subtitle', and 'ticker' to identify the teams, and then use the 'close_time' field -- after subtracting exactly 2 years from it -- to get the game start time that can be used (along with team names) to link the Kalshi odds for this market to the games table.
- For The Odds API, collect odds for sportsbooks in both the 'us' and 'eu' regions. Use the 'sports/baseball_mlb/odds' endpoint and find the associated games for each set of odds by using the 'home_team', 'away_team', and 'commence_time' fields (but note that 'commence_time' should be fuzzily matched to the games, as sometimes it's off by a few minutes or so). 
- For all sportsbooks and prediction markets, we should store both the actual raw odds (in decimal notation) alongside a de-vigged version of the odds that uses a constant exponent on all raw outcomes odds to normalize to a summed probability (across outcomes) of 1. Make sure to use the constant exponent method, not the additive, multiplicative, or Shin de-vigging methods.
- We'll restrict this analysis to sports markets only (e.g. not political bets), as the outcomes are easily definable.
- We'll only look at odds for single-match outcomes, no parlays or prop bets or season standings/tables bets.
- We'll only analyze odds up to the start of each event (not live or in-game odds). 
- For markets where each outcome can have both Yes and No bets, we'll only analyze the Yes part for each outcome (as the No bets would be somewhat duplicative).
- Let's start with Major League Baseball moneyline odds (which have binary outcomes: home win / away win), as this league is currently in season and has many games each day to start building a dataset from.
- However, note that the logic (and therefore the accompanying database schema) should be generalizable to markets with ternary outcomes (e.g. in soccer, where it's typically home win / away win / draw). Plan to add Premier League ternary-outcome matches when that season starts.
- The data schema should be set up in a way that would make it easy to query data to answer questions like 'Which platform or bookie has the most accurate odds in the 15 minutes prior to match start?"
- This means that individual games must be a standardized entity - that is, even if markets are worded differently on each platform (see 'Additional Context' section below), they must all link back to the same game when applicable.
- Right now no UI component is required.

## Additional Context

- Markets and outcomes will be worded differently on different platforms. As a hypothetical example, a Red Sox vs. Yankees game may be "BOS vs. NYY" on one platform but "Red Sox vs. Yankees" on another or even "Boston Red Sox vs. New York Yankees" on a third. So the cross-platform market matching criteria (in order to link all of these markets to the same game entity) should be fairly broad, but not so broad that it conflates, say, the Boston Red Sox with the Chicago White Sox or the Cincinnati Reds.
- It's important to disambiguate by date and game start time as well. In baseball especially, games between teams are typically played in a series, so the Red Sox may play the Yankees 3 days in a row. It is important that a market for, e.g. Red Sox-Yankees on July 30th not be confused with the game between the same teams on July 31st. Similarly, occasionally there are doubleheaders: 2 games between the same teams on the same date. In that case, use game start times to disambiguate. The start time matching can be fuzzy to account for small discrepancies (say, up to 30 minutes) but certainly nothing more than 3 hours.

Feel free to ask any clarifying questions.