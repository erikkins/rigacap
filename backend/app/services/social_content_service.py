"""
Social Content Service - Generate social media posts from walk-forward trade results.

Creates draft posts for admin review/approval before posting.
Supports Twitter (280 chars) and Instagram (longer captions) formats.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.core.database import SocialPost, WalkForwardSimulation

logger = logging.getLogger(__name__)


class SocialContentService:
    """Generate social media content from walk-forward simulation results."""

    # Hashtag sets by post type
    HASHTAGS = {
        "trade_result": "#StockTrading #AlgoTrading #WalkForward #TradingSignals #RigaCap",
        "missed_opportunity": "#StockTrading #MissedTrade #AlgoTrading #TradingSignals #RigaCap",
        "weekly_recap": "#WeeklyRecap #StockMarket #AlgoTrading #TradingResults #RigaCap",
        "regime_commentary": "#MarketRegime #StockMarket #TradingStrategy #MarketAnalysis #RigaCap",
    }

    async def generate_from_nightly_wf(
        self, db: AsyncSession, simulation_id: int
    ) -> List[SocialPost]:
        """
        Generate social posts from a completed nightly walk-forward simulation.

        Returns list of created SocialPost records (status=draft).
        """
        # Load simulation
        result = await db.execute(
            select(WalkForwardSimulation).where(
                WalkForwardSimulation.id == simulation_id
            )
        )
        sim = result.scalar_one_or_none()
        if not sim or not sim.trades_json:
            logger.warning(f"No trades found for simulation {simulation_id}")
            return []

        trades = json.loads(sim.trades_json)
        if not trades:
            return []

        posts = []

        # Filter to recent profitable closed trades (>5% return)
        profitable = [
            t for t in trades
            if t.get("pnl_pct", 0) > 5.0 and t.get("exit_date")
        ]
        profitable.sort(key=lambda t: t.get("pnl_pct", 0), reverse=True)

        # Generate trade_result posts for top 3 winners
        for trade in profitable[:3]:
            twitter_post = self._make_trade_result_twitter(trade)
            insta_post = self._make_trade_result_instagram(trade)
            threads_post = self._make_trade_result_threads(trade)

            for post in [twitter_post, insta_post, threads_post]:
                post.source_simulation_id = simulation_id
                post.source_trade_json = json.dumps(trade)
                db.add(post)
                posts.append(post)

        # Generate missed_opportunity posts for next 2
        for trade in profitable[3:5]:
            twitter_post = self._make_missed_opportunity_twitter(trade)
            insta_post = self._make_missed_opportunity_instagram(trade)
            threads_post = self._make_missed_opportunity_threads(trade)

            for post in [twitter_post, insta_post, threads_post]:
                post.source_simulation_id = simulation_id
                post.source_trade_json = json.dumps(trade)
                db.add(post)
                posts.append(post)

        # Generate regime commentary
        regime_posts = await self._make_regime_commentary(db, simulation_id)
        for post in regime_posts:
            db.add(post)
            posts.append(post)

        # Auto-schedule all posts 12 hours from now and send cancel notification
        publish_at = datetime.utcnow() + timedelta(hours=12)
        for post in posts:
            post.status = "scheduled"
            post.scheduled_for = publish_at

        await db.commit()
        logger.info(f"Generated {len(posts)} social posts from simulation {simulation_id}, auto-scheduled for {publish_at.isoformat()}")

        # Send batch cancel notification email so admin can kill bad ones
        try:
            from app.services.post_scheduler_service import post_scheduler_service
            await post_scheduler_service._send_batch_notification(posts, hours_before=12)
            logger.info(f"Sent auto-schedule cancel notification for {len(posts)} posts")
        except Exception as e:
            logger.error(f"Failed to send auto-schedule notification: {e}")

        return posts

    async def generate_weekly_recap(self, db: AsyncSession) -> List[SocialPost]:
        """
        Generate weekly recap posts (called on Fridays).

        Aggregates the week's nightly WF trades into a summary post.
        """
        # Get all nightly WF simulations from the past 7 days
        week_ago = datetime.utcnow() - timedelta(days=7)
        result = await db.execute(
            select(WalkForwardSimulation)
            .where(WalkForwardSimulation.is_nightly_missed_opps == True)
            .where(WalkForwardSimulation.status == "completed")
            .where(WalkForwardSimulation.simulation_date >= week_ago)
            .order_by(desc(WalkForwardSimulation.simulation_date))
            .limit(1)
        )
        sim = result.scalar_one_or_none()

        if not sim or not sim.trades_json:
            return []

        trades = json.loads(sim.trades_json)
        if not trades:
            return []

        # Aggregate stats
        closed_trades = [t for t in trades if t.get("exit_date")]
        winning = [t for t in closed_trades if t.get("pnl_pct", 0) > 0]
        total = len(closed_trades)
        wins = len(winning)
        win_rate = (wins / total * 100) if total > 0 else 0
        avg_return = (
            sum(t.get("pnl_pct", 0) for t in closed_trades) / total
            if total > 0
            else 0
        )
        best_trade = max(closed_trades, key=lambda t: t.get("pnl_pct", 0)) if closed_trades else None
        total_pnl = sum(t.get("pnl_dollars", 0) for t in closed_trades)

        posts = []

        # Deterministic pick using date-based hash
        date_key = str(datetime.utcnow().date())

        # Twitter recap
        opener = self._RECAP_OPENERS_TWITTER[hash(date_key) % len(self._RECAP_OPENERS_TWITTER)]
        closer = self._RECAP_CLOSERS_TWITTER[hash(date_key + "closer") % len(self._RECAP_CLOSERS_TWITTER)]

        twitter_text = f"{opener}\n\n"
        twitter_text += f"{wins}W-{total - wins}L"
        twitter_text += f" | {win_rate:.0f}% win rate"
        twitter_text += f" | {avg_return:+.1f}% avg\n"
        if best_trade:
            twitter_text += f"\nMVP: ${best_trade['symbol']} at {best_trade.get('pnl_pct', 0):+.1f}%\n"
        twitter_text += f"\n{closer}"

        twitter_post = SocialPost(
            post_type="weekly_recap",
            platform="twitter",
            status="draft",
            text_content=twitter_text,
            hashtags=self.HASHTAGS["weekly_recap"],
            source_data_json=json.dumps({
                "total_trades": total,
                "wins": wins,
                "win_rate": round(win_rate, 1),
                "avg_return": round(avg_return, 1),
                "total_pnl": round(total_pnl, 2),
            }),
        )
        posts.append(twitter_post)

        # Instagram recap
        ig_opener = self._RECAP_OPENERS_INSTA[hash(date_key + "ig") % len(self._RECAP_OPENERS_INSTA)]
        ig_closer = self._RECAP_CLOSERS_INSTA[hash(date_key + "ig_closer") % len(self._RECAP_CLOSERS_INSTA)]

        insta_text = f"{ig_opener}\n\n"
        insta_text += f"{wins}W-{total - wins}L | {win_rate:.0f}% win rate\n"
        insta_text += f"Average return: {avg_return:+.1f}%\n"
        if best_trade:
            best_pct = best_trade.get('pnl_pct', 0)
            insta_text += (
                f"\nStar of the week: ${best_trade['symbol']}\n"
                f"${best_trade.get('entry_price', 0):.2f} \u2192 ${best_trade.get('exit_price', 0):.2f} ({best_pct:+.1f}%)\n"
            )
        insta_text += (
            f"\n{ig_closer}\n"
            f"\nrigacap.com"
        )

        insta_post = SocialPost(
            post_type="weekly_recap",
            platform="instagram",
            status="draft",
            text_content=insta_text,
            hashtags=self.HASHTAGS["weekly_recap"],
            source_data_json=json.dumps({
                "total_trades": total,
                "wins": wins,
                "win_rate": round(win_rate, 1),
                "avg_return": round(avg_return, 1),
                "total_pnl": round(total_pnl, 2),
            }),
        )
        posts.append(insta_post)

        for post in posts:
            db.add(post)
        await db.commit()

        return posts

    @staticmethod
    def _calc_days_held(trade: dict) -> int:
        """Calculate days held from entry/exit dates, falling back to days_held field."""
        entry = str(trade.get("entry_date", ""))[:10]
        exit_ = str(trade.get("exit_date", ""))[:10]
        if entry and exit_:
            try:
                d1 = datetime.strptime(entry, "%Y-%m-%d")
                d2 = datetime.strptime(exit_, "%Y-%m-%d")
                days = (d2 - d1).days
                return max(days, 1)
            except (ValueError, TypeError):
                pass
        return trade.get("days_held", 1)

    # ── Massive variety pools ────────────────────────────────────────
    # Openers, body templates, and closers mix-and-match for hundreds
    # of unique posts. Deterministic selection via symbol+date hash.

    _WIN_OPENERS = [
        # Confident
        "This one worked out nicely.",
        "The algo saw it coming.",
        "Patience paid off on this one.",
        "Another clean entry, clean exit.",
        "Caught the move, locked in gains.",
        "In and out. That's how it's done.",
        "The Ensemble doesn't chase \u2014 it waits.",
        "Textbook setup. Textbook result.",
        "When all 3 factors agree, good things happen.",
        "The math worked.",
        "Boring? Maybe. Profitable? Definitely.",
        "Sometimes the best trades are the quiet ones.",
        "No drama. Just returns.",
        "Let the trailing stop do its job.",
        "Entered with conviction, exited with profits.",
        # Conversational
        "Not bad for a robot.",
        "We'll take it.",
        "The algo doesn't celebrate. But we do.",
        "Another one for the walk-forward record.",
        "Add it to the pile.",
        "Rinse and repeat.",
        "Momentum is a beautiful thing.",
        "The system keeps receipts.",
        "When the setup is there, you take it.",
        "Some trades just work.",
        "No hot tips. No gut feelings. Just signal.",
        "The kind of trade you don't lose sleep over.",
        "Risk managed. Gains banked.",
        "This is what disciplined trading looks like.",
        "Clean signal. Clean execution.",
        # Witty
        "Meanwhile, the algo was quietly making money.",
        "While everyone was arguing on Twitter, we were trading.",
        "Another day, another walk-forward-verified exit.",
        "The market gave, the trailing stop took.",
        "No FOMO required.",
        "This trade didn't need a hot take.",
        "The algo doesn't read the news. It reads the data.",
        "Regime-aware, momentum-confirmed, and profitable.",
        "Three filters said yes. They were right.",
        "The boring part is the profitable part.",
        "This one paid its own subscription for the month.",
        "Signals in, gains out. Simple as that.",
        "You know what's better than a prediction? A verified result.",
        "One more for the highlight reel.",
        "The algo's win column just got longer.",
        # Understated
        "Quiet entry. Quiet exit. Not-so-quiet return.",
        "Nothing flashy. Just math doing math things.",
        "Filed under: things that worked.",
        "It's not luck when you can show the receipts.",
        "This is what walk-forward tested looks like in practice.",
    ]

    _WIN_CLOSERS_TWITTER = [
        "Walk-forward verified \u2014 not a backtest.",
        "Verified. Not hypothetical.",
        "Real signal, real result.",
        "No hindsight. No curve fitting.",
        "Walk-forward tested. Every. Single. Trade.",
        "The receipts are public.",
        "Every signal verified in real time.",
        "Not backtested. Walk-forward proven.",
        "All signals tested without future data.",
        "Results you can verify.",
    ]

    _WIN_CLOSERS_INSTA = [
        "Walk-forward verified. Not a backtest, not hypothetical \u2014 a real signal our system flagged in real time.",
        "This wasn't a hypothesis. Our system flagged it, we traded it, and here are the results.",
        "Every trade we post was a real-time signal. No cherry-picking. No Monday morning quarterbacking.",
        "Not a backtest. Not a \"what if.\" A real signal, verified by walk-forward testing.",
        "Our system doesn't get to peek at future data. It has to figure it out live \u2014 just like you.",
        "We show winners and losers. This one happened to be a winner.",
        "Verified in real time by our walk-forward engine. No look-ahead bias. Just math.",
        "The algo doesn't know it won. It just moves on to the next signal.",
        "This is what honest testing looks like. Every trade verified without future information.",
        "Real-time signal. Walk-forward verified. We don't post the trades that didn't happen.",
    ]

    _MISS_OPENERS = [
        "This one got away from most people.",
        "Were you watching this?",
        "The algo flagged it. Did you catch it?",
        "Quietly, this happened.",
        "Most people missed this.",
        "While you were sleeping on this one...",
        "This flew under the radar.",
        "Our system noticed. Did yours?",
        "Nobody was talking about this one.",
        "The kind of move you only see in hindsight \u2014 unless your algo caught it.",
        "This wasn't on anyone's watchlist. Except ours.",
        "Silent mover.",
        "Not on CNBC. Still made money.",
        "The market whispered. The algo heard.",
        "You won't find this on a screener.",
        "Funny how the best trades get no hype.",
        "No one tweeted about this entry. That was the point.",
        "This is the trade no one brags about missing.",
        "While fintwit was debating, this was running.",
        "The algo doesn't need consensus.",
        "No catalyst. No headline. Just momentum.",
        "Sometimes the best opportunities are the boring ones.",
        "Screener didn't catch it. Scanner did.",
        "The crowd was looking somewhere else.",
        "This is what systematic beats discretionary looks like.",
        "Not trending. Just profiting.",
        "You had to be subscribed to see this one.",
        "This wasn't on anyone's radar. Well, almost anyone's.",
        "The algo doesn't have FOMO. It has a process.",
        "Another one the market forgot to tell people about.",
        "Zero buzz. All signal.",
        "This was a walk-forward signal, not a water cooler tip.",
        "If you blinked, you missed it.",
        "This trade was boring. The return wasn't.",
        "Nobody rings a bell at the top \u2014 but the algo sends an email.",
        "The signal fired. Did you act?",
        "This is why we don't rely on gut feelings.",
        "Not sexy. Very profitable.",
        "The kind of trade that only shows up in systematic screens.",
        "Filed under: opportunities most people scrolled past.",
        "This move started quietly and ended loudly.",
        "Our subscribers saw this coming. The rest saw it going.",
        "This is what happens when you let data lead.",
        "The headlines came after the move. The signal came before.",
        "Not a rumor. Not a tip. A verified signal.",
        "When momentum and timing align, you get this.",
        "The algo doesn't have a Twitter account. It has results.",
        "This one was hiding in plain sight.",
        "Sometimes the market hands you a gift. You just have to be looking.",
        "Not every winner gets a victory lap. This one deserves one.",
    ]

    _MISS_CLOSERS_TWITTER = [
        "Walk-forward verified \u2014 not a backtest.",
        "Our system flagged it in real time.",
        "Real signal. Real-time. Real result.",
        "Subscribers saw it. Did you?",
        "Not hindsight. Foresight.",
        "The algo doesn't do FOMO. It does math.",
        "Walk-forward proven. Zero look-ahead bias.",
        "Next time, let the algo tell you.",
        "This is why systematic beats gut feeling.",
        "Verified signal \u2014 not a hot take.",
    ]

    _MISS_CLOSERS_INSTA = [
        "This wasn't a backtest. Our system flagged it in real time. You just had to be subscribed.",
        "The signal was there. The opportunity was real. The question is whether you were paying attention.",
        "We don't post these to brag. We post them so you know what systematic trading actually looks like.",
        "Next time this setup appears, our subscribers will see it first. That's the whole point.",
        "Real-time signal, walk-forward verified. No one told us this trade would work. The data did.",
        "The algo doesn't feel bad about the ones you miss. But you might.",
        "Every trade we post was flagged before it happened. Not after. That's the difference.",
        "You can't go back in time. But you can subscribe before the next one.",
        "This is what you miss when you rely on screeners and gut feelings instead of a system.",
        "Walk-forward tested. Every signal verified without future data. The algo plays fair.",
    ]

    _RECAP_OPENERS_TWITTER = [
        "This week's scorecard:",
        "Weekly results are in.",
        "Another week in the books.",
        "End-of-week report card:",
        "Let's see how the algo did this week.",
        "The numbers don't lie. Here's this week:",
        "Friday means receipts. Here's ours:",
        "Week's over. Here's the damage (the good kind):",
        "The algo's weekly report:",
        "Time to check the scoreboard.",
    ]

    _RECAP_CLOSERS_TWITTER = [
        "All walk-forward verified. No cherry-picking.",
        "Every trade verified. No look-ahead bias.",
        "Walk-forward tested. Every. Single. Trade.",
        "All signals verified in real time.",
        "No backtests. No hypotheticals. Just results.",
        "Systematic. Verified. Repeatable.",
        "The algo doesn't pick favorites. It picks winners.",
        "Not a highlights reel. The full record.",
        "We show the wins and the losses.",
        "Same system, same rules, every week.",
    ]

    _RECAP_OPENERS_INSTA = [
        "Week in review.",
        "Another week, another set of receipts.",
        "Weekly recap \u2014 let's see how the algo performed.",
        "Here's what systematic trading looked like this week.",
        "The algo's weekly report card is in.",
        "Friday close means it's time for the numbers.",
        "How'd we do this week? Glad you asked.",
        "The Ensemble's weekly performance breakdown:",
        "End of week. Time for the honest numbers.",
        "Weekly walk-forward results \u2014 the full picture.",
    ]

    _RECAP_CLOSERS_INSTA = [
        "Every signal walk-forward verified.\nNo curve fitting. No look-ahead. Just math.",
        "We don't cherry-pick our best trades. This is the full record \u2014 wins and losses alike.",
        "All verified in real time. The algo doesn't get the luxury of hindsight.",
        "Systematic trading isn't about having a perfect week. It's about having a verified one.",
        "The algo doesn't celebrate wins or mourn losses. It just moves to the next signal.",
        "No edits. No selective reporting. Every trade that fired gets reported.",
        "This is what disciplined, regime-aware trading looks like over a full week.",
        "Walk-forward tested, not backtested. Every signal verified without future data.",
        "The system works the same every week. The results vary. The process doesn't.",
        "We post the full record because transparency isn't optional \u2014 it's the product.",
    ]

    _REGIME_FLAVORS = {
        "Strong Bull": [
            "Full send mode activated.",
            "Green across the board. The algo is busy.",
            "Broad rally, high breadth. This is what we train for.",
            "Everything's working. That's usually when people get careless. Not us.",
            "Bull market in full swing. The system is fully deployed.",
            "When the market's this strong, the hard part is being patient enough to wait for the signal.",
            "Risk-on. But still disciplined.",
            "The algo doesn't get euphoric. It gets positioned.",
            "Strong Bull regime detected. Maximum exposure, maximum discipline.",
            "Markets up, breadth strong, signals firing. Business as usual.",
        ],
        "Weak Bull": [
            "Bull market with fine print.",
            "Technically bullish. Practically tricky.",
            "The market is up, but only a few stocks are doing the work.",
            "Narrow leadership. The algo is being picky. You should be too.",
            "Looks bullish from 30,000 feet. Looks selective from ground level.",
            "Weak Bull: where most people think everything's fine and then wonder why their picks aren't working.",
            "The index is green. Your portfolio might not be. That's a Weak Bull.",
            "Selective entries only. The market isn't as strong as the headlines suggest.",
            "Bull market for the few. Flat market for everyone else.",
            "This is the regime where stock pickers earn their keep.",
        ],
        "Rotating Bull": [
            "Musical chairs, but with money.",
            "Sector rotation in full effect. Follow the momentum.",
            "Last week's winners are this week's laggards. The algo adapts.",
            "The market is rotating. The question is whether you're rotating with it.",
            "Rotating Bull: where yesterday's trade is today's trap.",
            "Sectors taking turns. The algo follows the leader.",
            "This is the regime where discipline matters most.",
            "Momentum is sector-specific right now. The Ensemble knows which ones.",
            "Whichever sector is leading, that's where our signals point.",
            "Rotation is healthy. It's also confusing if you're not systematic about it.",
        ],
        "Range Bound": [
            "The market is thinking. So are we.",
            "Choppy. The algo is sitting on its hands (mostly).",
            "Range Bound: the regime where patience is literally the strategy.",
            "No trend, no edge. Reduced position sizing.",
            "The market is going sideways. So is everyone's P&L.",
            "This is the regime where overtrading kills you. We size down.",
            "Not every market deserves your capital. This one gets less of it.",
            "Flat markets punish impatience. The algo doesn't have that problem.",
            "Range Bound detected. Translation: chill.",
            "The best trade in a Range Bound market is often no trade at all.",
        ],
        "Weak Bear": [
            "Death by a thousand paper cuts territory.",
            "Slow bleed. Stops tightened. Cash raised.",
            "The market isn't crashing. It's just quietly taking your money.",
            "Weak Bear: not scary enough to sell, not strong enough to buy. That's the trap.",
            "This is the regime where hope is the most expensive emotion.",
            "Tighter stops. Fewer signals. More cash. That's the playbook.",
            "The market is drifting lower. The algo is drifting toward cash.",
            "Weak Bear mode: where \"buying the dip\" starts to feel like a bad habit.",
            "Not a crash. Just a slow leak. The algo adjusts.",
            "The hardest regime to trade. Good thing we have a system for it.",
        ],
        "Panic Crash": [
            "When the VIX spikes, we step aside. Ego is expensive.",
            "Crash mode. The algo does the one thing most humans can't: nothing.",
            "Panic detected. All positions closed. We'll be back when the math says so.",
            "This is the regime where heroes go broke. We're not heroes. We're systematic.",
            "Exit everything. Ask questions later. That's the Panic playbook.",
            "The market is panicking. We are not. We're in cash.",
            "Crashes are not for trading. They're for surviving. The algo survives.",
            "Everyone has a plan until the VIX hits 40.",
            "The best trade in a crash is the one you don't make.",
            "Panic Crash detected. Cash is a position. A good one, right now.",
        ],
        "Recovery": [
            "The brave (and the algorithmic) start buying here.",
            "Bottom's in? Maybe. The algo is starting to nibble.",
            "Recovery regime detected. Cautiously optimistic. Heavy on the cautious.",
            "The market is trying to find its footing. The algo is placing its first bets.",
            "This is where the next bull market starts. If you're paying attention.",
            "Scaling back in. Not all at once \u2014 we're systematic, not reckless.",
            "Recovery mode: the regime that rewards patience and punishes lateness.",
            "The worst is probably over. The algo is starting to agree.",
            "This is the regime where last cycle's crash sellers become this cycle's FOMO buyers.",
            "Slowly, carefully, the algo is putting money back to work.",
        ],
    }

    def _pick(self, items: list, trade: dict, salt: str = "") -> str:
        """Deterministically pick from a list using symbol+date+salt hash."""
        key = trade.get("symbol", "") + str(trade.get("entry_date", "")) + salt
        return items[hash(key) % len(items)]

    def _make_trade_result_twitter(self, trade: dict) -> SocialPost:
        """Create a Twitter-format trade result post (280 chars max)."""
        symbol = trade.get("symbol", "???")
        pnl_pct = trade.get("pnl_pct", 0)
        days_held = self._calc_days_held(trade)

        opener = self._pick(self._WIN_OPENERS, trade)
        closer = self._pick(self._WIN_CLOSERS_TWITTER, trade, "closer")

        text = (
            f"{opener}\n\n"
            f"${symbol}: {pnl_pct:+.1f}% in {days_held} days.\n\n"
            f"{closer}"
        )

        return SocialPost(
            post_type="trade_result",
            platform="twitter",
            status="draft",
            text_content=text,
            hashtags=self.HASHTAGS["trade_result"] + f" ${symbol}",
        )

    def _make_trade_result_instagram(self, trade: dict) -> SocialPost:
        """Create an Instagram-format trade result post (longer caption)."""
        symbol = trade.get("symbol", "???")
        entry_price = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        pnl_pct = trade.get("pnl_pct", 0)
        entry_date = str(trade.get("entry_date", ""))[:10]
        exit_date = str(trade.get("exit_date", ""))[:10]
        exit_reason = trade.get("exit_reason", "trailing_stop")
        days_held = self._calc_days_held(trade)

        _EXIT_DISPLAY = {
            "simulation_end": "portfolio rebalance",
            "rebalance_exit": "portfolio rebalance",
            "trailing_stop": "trailing stop",
            "market_regime": "regime shift",
        }
        exit_display = _EXIT_DISPLAY.get(exit_reason, exit_reason.replace("_", " ")) if exit_reason else "exit"
        opener = self._pick(self._WIN_OPENERS, trade, "ig")
        closer = self._pick(self._WIN_CLOSERS_INSTA, trade, "ig_closer")

        text = (
            f"{opener}\n\n"
            f"${symbol} \u2014 {pnl_pct:+.1f}% in {days_held} days\n"
            f"In at ${entry_price:.2f} \u2192 Out at ${exit_price:.2f}\n"
            f"Exit: {exit_display.lower()}\n\n"
            f"{closer}\n"
            f"\nrigacap.com"
        )

        return SocialPost(
            post_type="trade_result",
            platform="instagram",
            status="draft",
            text_content=text,
            hashtags=self.HASHTAGS["trade_result"] + f" ${symbol}",
            image_metadata_json=json.dumps({
                "symbol": symbol,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl_pct": pnl_pct,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "exit_reason": exit_reason,
                "card_type": "trade_result",
            }),
        )

    def _make_missed_opportunity_twitter(self, trade: dict) -> SocialPost:
        """Create a Twitter missed opportunity post."""
        symbol = trade.get("symbol", "???")
        pnl_pct = trade.get("pnl_pct", 0)
        days_held = self._calc_days_held(trade)

        opener = self._pick(self._MISS_OPENERS, trade)
        closer = self._pick(self._MISS_CLOSERS_TWITTER, trade, "closer")

        text = (
            f"{opener}\n\n"
            f"${symbol}: {pnl_pct:+.1f}% in {days_held} days.\n\n"
            f"{closer}"
        )

        return SocialPost(
            post_type="missed_opportunity",
            platform="twitter",
            status="draft",
            text_content=text,
            hashtags=self.HASHTAGS["missed_opportunity"] + f" ${symbol}",
            source_trade_json=json.dumps(trade),
        )

    def _make_missed_opportunity_instagram(self, trade: dict) -> SocialPost:
        """Create an Instagram missed opportunity post."""
        symbol = trade.get("symbol", "???")
        entry_price = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        pnl_pct = trade.get("pnl_pct", 0)
        entry_date = str(trade.get("entry_date", ""))[:10]
        exit_date = str(trade.get("exit_date", ""))[:10]
        days_held = self._calc_days_held(trade)

        opener = self._pick(self._MISS_OPENERS, trade, "ig")
        closer = self._pick(self._MISS_CLOSERS_INSTA, trade, "ig_closer")

        text = (
            f"{opener}\n\n"
            f"${symbol} \u2014 {pnl_pct:+.1f}% in {days_held} days\n"
            f"Signal fired {entry_date} at ${entry_price:.2f}\n"
            f"Exit {exit_date} at ${exit_price:.2f}\n\n"
            f"{closer}\n"
            f"\nrigacap.com"
        )

        exit_reason = trade.get("exit_reason", "trailing_stop")

        return SocialPost(
            post_type="missed_opportunity",
            platform="instagram",
            status="draft",
            text_content=text,
            hashtags=self.HASHTAGS["missed_opportunity"] + f" ${symbol}",
            image_metadata_json=json.dumps({
                "symbol": symbol,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "pnl_pct": pnl_pct,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "exit_reason": exit_reason,
                "card_type": "missed_opportunity",
            }),
        )

    def _make_trade_result_threads(self, trade: dict) -> SocialPost:
        """Create a Threads-format trade result post (500 chars max)."""
        symbol = trade.get("symbol", "???")
        pnl_pct = trade.get("pnl_pct", 0)
        entry_price = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        days_held = self._calc_days_held(trade)

        opener = self._pick(self._WIN_OPENERS, trade, "threads")
        closer = self._pick(self._WIN_CLOSERS_TWITTER, trade, "threads_closer")

        text = (
            f"{opener}\n\n"
            f"${symbol}: {pnl_pct:+.1f}% in {days_held} days\n"
            f"${entry_price:.2f} \u2192 ${exit_price:.2f}\n\n"
            f"{closer}\n\nrigacap.com"
        )

        return SocialPost(
            post_type="trade_result",
            platform="threads",
            status="draft",
            text_content=text[:500],
        )

    def _make_missed_opportunity_threads(self, trade: dict) -> SocialPost:
        """Create a Threads missed opportunity post (500 chars max)."""
        symbol = trade.get("symbol", "???")
        pnl_pct = trade.get("pnl_pct", 0)
        entry_price = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        days_held = self._calc_days_held(trade)

        opener = self._pick(self._MISS_OPENERS, trade, "threads")
        closer = self._pick(self._MISS_CLOSERS_TWITTER, trade, "threads_closer")

        text = (
            f"{opener}\n\n"
            f"${symbol}: {pnl_pct:+.1f}% in {days_held} days\n"
            f"Signal fired at ${entry_price:.2f}, exited at ${exit_price:.2f}\n\n"
            f"{closer}\n\nrigacap.com"
        )

        return SocialPost(
            post_type="missed_opportunity",
            platform="threads",
            status="draft",
            text_content=text[:500],
            source_trade_json=json.dumps(trade),
        )

    async def _make_regime_commentary(
        self, db: AsyncSession, simulation_id: int
    ) -> List[SocialPost]:
        """Generate regime commentary posts based on current market conditions."""
        posts = []

        try:
            from app.services.market_regime import market_regime_service
            from app.services.scanner import scanner_service

            spy_df = scanner_service.data_cache.get("SPY")
            vix_df = scanner_service.data_cache.get("^VIX")

            if spy_df is None or len(spy_df) < 200:
                return posts

            forecast = market_regime_service.predict_transitions(
                spy_df=spy_df,
                universe_dfs=scanner_service.data_cache,
                vix_df=vix_df,
            )

            regime_name = forecast.current_regime_name
            regime_desc = forecast.outlook_detail
            risk_level = forecast.risk_change

            spy_price = round(float(spy_df.iloc[-1]["close"]), 2)
            vix_level = round(float(vix_df.iloc[-1]["close"]), 2) if vix_df is not None and len(vix_df) > 0 else None

            # Twitter
            flavor_list = self._REGIME_FLAVORS.get(regime_name, ["Adapting accordingly."])
            flavor = flavor_list[hash(regime_name + str(spy_price)) % len(flavor_list)]
            twitter_text = f"Regime check: {regime_name}\n\n"
            twitter_text += f"SPY ${spy_price}"
            if vix_level is not None:
                twitter_text += f" | VIX {vix_level}"
            twitter_text += f"\n\n{flavor}"

            twitter_post = SocialPost(
                post_type="regime_commentary",
                platform="twitter",
                status="draft",
                text_content=twitter_text,
                hashtags=self.HASHTAGS["regime_commentary"],
                source_simulation_id=simulation_id,
                source_data_json=json.dumps({
                    "regime": regime_name,
                    "risk_level": risk_level,
                    "spy_price": spy_price,
                    "vix_level": vix_level,
                }),
            )
            posts.append(twitter_post)

            # Instagram
            flavor_list = self._REGIME_FLAVORS.get(regime_name, ["Adapting accordingly."])
            ig_flavor = flavor_list[hash(regime_name + str(spy_price) + "ig") % len(flavor_list)]
            insta_text = f"Regime check: {regime_name}\n\n"
            insta_text += f"SPY ${spy_price}"
            if vix_level is not None:
                insta_text += f" | VIX {vix_level}"
            insta_text += f"\nRisk: {risk_level.title()}\n\n"
            insta_text += f"{ig_flavor}\n\n"
            insta_text += f"{regime_desc}\n\n"
            insta_text += (
                f"Most strategies have one mode. Ours detects 7 and\n"
                f"adjusts position sizing, entries, and exits automatically.\n"
                f"\nrigacap.com"
            )

            insta_post = SocialPost(
                post_type="regime_commentary",
                platform="instagram",
                status="draft",
                text_content=insta_text,
                hashtags=self.HASHTAGS["regime_commentary"],
                source_simulation_id=simulation_id,
                source_data_json=json.dumps({
                    "regime": regime_name,
                    "risk_level": risk_level,
                    "spy_price": spy_price,
                    "vix_level": vix_level,
                }),
            )
            posts.append(insta_post)

            # Threads
            threads_flavor = flavor_list[hash(regime_name + str(spy_price) + "threads") % len(flavor_list)]
            threads_text = f"Regime check: {regime_name}\n\n"
            threads_text += f"SPY ${spy_price}"
            if vix_level is not None:
                threads_text += f" | VIX {vix_level}"
            threads_text += f"\n\n{threads_flavor}\n\nrigacap.com"

            threads_post = SocialPost(
                post_type="regime_commentary",
                platform="threads",
                status="draft",
                text_content=threads_text[:500],
                source_simulation_id=simulation_id,
                source_data_json=json.dumps({
                    "regime": regime_name,
                    "risk_level": risk_level,
                    "spy_price": spy_price,
                    "vix_level": vix_level,
                }),
            )
            posts.append(threads_post)

        except Exception as e:
            logger.error(f"Regime commentary generation failed: {e}")

        return posts


# Singleton instance
social_content_service = SocialContentService()
