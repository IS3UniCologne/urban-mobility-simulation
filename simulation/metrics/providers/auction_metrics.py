"""Auction metrics module."""

from __future__ import annotations


from ..metrics_base import MetricsBase
from ..metrics_dict import MetricsDict
from simulation.world.markets.shared_charging_auction import SharedChargingAuction



class AuctionMetrics(MetricsBase):
    """
    Metrics class for auction-specific metrics.

    Provides aggregated metrics for available and cleared capacity, bidding behaviors, and clearing prices.
    Tracks the state of the *last cleared* auction and explicitly includes the timeslot it corresponds to.
    """

    def to_dict(self) -> MetricsDict:
        """Return metrics for the auctions in the simulation."""
        if self._simulation.world.charging_infrastructures is None:
            return MetricsDict()

        metrics = MetricsDict()
        aggregate = {
            "auction_timeslot": -1,
            "total_available_capacity": 0,
            "total_cleared_capacity": 0,
            "total_bidded_capacity": 0,
            "total_bids_count": 0,
            "avg_clearing_price": 0.0,
            "avg_bid_price": 0.0,
        }

        # For tracking sums that go into averages
        sum_clearing_price = 0.0
        sum_bid_price = 0.0

        for idx, infrastructure in enumerate(self._simulation.world.charging_infrastructures):
            if hasattr(infrastructure, "auction") and infrastructure.auction is not None:
                auction = infrastructure.auction
                if isinstance(auction, SharedChargingAuction):
                    auction_metrics = self._get_shared_auction_metrics(auction)
                    metrics[f"infrastructure_{idx}"] = auction_metrics

                    # Add to global aggregates
                    agg = auction_metrics["aggregate"]
                    if isinstance(agg, dict):
                        # Taking the timeslot from the first infrastructure (they should be synced anyway)
                        aggregate["auction_timeslot"] = agg["auction_timeslot"]
                        aggregate["total_available_capacity"] += agg["available_capacity"]
                        aggregate["total_cleared_capacity"] += agg["cleared_capacity"]
                        aggregate["total_bidded_capacity"] += agg["total_bidded_capacity"]
                        aggregate["total_bids_count"] += agg["bids_count"]
                        sum_clearing_price += (
                            agg["avg_clearing_price"] * agg["cleared_capacity"]
                        )
                        sum_bid_price += (
                            agg["avg_bid_price"] * agg["total_bidded_capacity"]
                        )

        if aggregate["total_cleared_capacity"] > 0:
            aggregate["avg_clearing_price"] = sum_clearing_price / aggregate["total_cleared_capacity"]
        
        if aggregate["total_bidded_capacity"] > 0:
            aggregate["avg_bid_price"] = sum_bid_price / aggregate["total_bidded_capacity"]

        metrics["aggregate"] = MetricsDict(aggregate)
        return metrics

    def _get_shared_auction_metrics(self, auction: SharedChargingAuction) -> MetricsDict:
        """Extract metrics from a SharedChargingAuction."""
        auction_metrics = MetricsDict()
        
        last_state = getattr(auction, "_last_auction_state", {})
        
        if not last_state:
            # Auction hasn't cleared yet
            return MetricsDict({
                "aggregate": MetricsDict({
                    "auction_timeslot": -1,
                    "available_capacity": 0,
                    "cleared_capacity": 0,
                    "total_bidded_capacity": 0,
                    "bids_count": 0,
                    "avg_clearing_price": 0.0,
                    "avg_bid_price": 0.0,
                })
            })

        timeslot = last_state.get("timeslot", -1)
        available_capacity_dict = last_state.get("available_capacity", {})
        bids_dict = last_state.get("bids", {})
        results_dict = last_state.get("results", {})

        total_available = 0
        total_cleared = 0
        total_bidded = 0
        total_bids = 0
        sum_clearing_price = 0.0
        sum_bid_price = 0.0

        for location, available_capacity in available_capacity_dict.items():
            loc_metrics = {
                "auction_timeslot": timeslot,
                "available_capacity": available_capacity,
                "cleared_capacity": 0,
                "clearing_price": 0.0,
                "total_bidded_capacity": 0,
                "bids_count": 0,
                "avg_bid_price": 0.0,
            }
            
            # Extract bid information
            if location in bids_dict:
                loc_bids = bids_dict[location]
                bids_count = len(loc_bids)
                bidded_cap = sum(bid[0] for bid in loc_bids)
                avg_price = sum(bid[0] * bid[1] for bid in loc_bids) / bidded_cap if bidded_cap > 0 else 0.0
                
                loc_metrics["bids_count"] = bids_count
                loc_metrics["total_bidded_capacity"] = bidded_cap
                loc_metrics["avg_bid_price"] = avg_price
                
                total_bidded += bidded_cap
                total_bids += bids_count
                sum_bid_price += avg_price * bidded_cap

            # Extract clearing information
            if location in results_dict:
                loc_results = results_dict[location]
                cleared_cap = sum(res[0] for res in loc_results.values())
                
                # For uniform pricing, clearing price is the same for all (or 0 if no one cleared)
                clearing_prices = [res[1] for res in loc_results.values() if res[0] > 0]
                clearing_price = clearing_prices[0] if clearing_prices else 0.0

                loc_metrics["cleared_capacity"] = cleared_cap
                loc_metrics["clearing_price"] = clearing_price
                
                total_cleared += cleared_cap
                sum_clearing_price += clearing_price * cleared_cap

            total_available += available_capacity
            auction_metrics[location] = MetricsDict(loc_metrics)
            
        # Infrastructure-level aggregates
        agg = {
            "auction_timeslot": timeslot,
            "available_capacity": total_available,
            "cleared_capacity": total_cleared,
            "total_bidded_capacity": total_bidded,
            "bids_count": total_bids,
            "avg_clearing_price": sum_clearing_price / total_cleared if total_cleared > 0 else 0.0,
            "avg_bid_price": sum_bid_price / total_bidded if total_bidded > 0 else 0.0,
        }
        
        auction_metrics["aggregate"] = MetricsDict(agg)
        return auction_metrics
