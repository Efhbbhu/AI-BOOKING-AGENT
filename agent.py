# Simplified LangGraph workflow for booking agent
from typing import Dict, List, Any, TypedDict, Optional, Tuple
from datetime import datetime, timezone, timedelta
from langgraph.graph import StateGraph, END
from tools import AvailabilityTool, PricingTool, DistanceTool
from llm import GroqLLM
from firebase import FirestoreClient

DUBAI_TZ = timezone(timedelta(hours=4))

class BookingState(TypedDict):
    """State object for the booking workflow"""
    query: str
    uid: str
    confirm: bool
    parsed_query: Optional[Dict[str, Any]]
    provider: Optional[Dict[str, Any]]
    available_slots: Optional[List[Dict]]
    pricing: Optional[Dict[str, Any]]
    proposal: Optional[Dict[str, Any]]
    booking_result: Optional[Dict[str, Any]]
    error: Optional[str]
    steps: Optional[List[Dict[str, Any]]]  # Track tool execution steps

class BookingAgent:
    """Simplified booking agent using LangGraph"""
    
    def __init__(self):
        self.llm = GroqLLM()
        self.distance_tool = DistanceTool()
        self.availability_tool = AvailabilityTool()
        self.pricing_tool = PricingTool()
        self.firestore_client = FirestoreClient()
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build simplified LangGraph workflow"""
        workflow = StateGraph(BookingState)
        
        # Add nodes
        workflow.add_node("parse_query", self._parse_query)
        workflow.add_node("find_provider", self._find_provider)
        workflow.add_node("check_availability", self._check_availability)
        workflow.add_node("calculate_pricing", self._calculate_pricing)
        workflow.add_node("create_proposal", self._create_proposal)
        workflow.add_node("finalize_booking", self._finalize_booking)
        
        # Set workflow
        workflow.set_entry_point("parse_query")
        
        # Add conditional edges to handle errors
        workflow.add_conditional_edges(
            "parse_query",
            self._check_for_error,
            {"continue": "find_provider", "error": END}
        )
        workflow.add_conditional_edges(
            "find_provider",
            self._check_for_error,
            {"continue": "check_availability", "error": END}
        )
        workflow.add_conditional_edges(
            "check_availability",
            self._check_for_error,
            {"continue": "calculate_pricing", "error": END}
        )
        workflow.add_conditional_edges(
            "calculate_pricing",
            self._check_for_error,
            {"continue": "create_proposal", "error": END}
        )
        
        # Conditional confirmation
        workflow.add_conditional_edges(
            "create_proposal",
            self._should_confirm,
            {"confirm": "finalize_booking", "end": END}
        )
        workflow.add_edge("finalize_booking", END)
        
        return workflow.compile()
    
    def _parse_query(self, state: BookingState) -> BookingState:
        """Parse natural language query"""
        step = {
            "tool": "LLM Query Parser",
            "action": "Parse natural language query",
            "input": state["query"],
            "status": "running"
        }

        if "steps" not in state or state["steps"] is None:
            state["steps"] = []

        try:
            parsed = self.llm.parse_booking_query(state["query"])

            if not parsed.get("valid_query", True):
                message = parsed.get("message", "Unable to understand your request.")
                step.update({
                    "status": "failed",
                    "output": message,
                    "details": parsed
                })
                state["steps"].append(step)
                state["error"] = message
                return state

            step.update({
                "status": "success",
                "output": f"Extracted service: {parsed.get('service')}, location: {parsed.get('location')}, time: {parsed.get('preferred_time', 'any')}",
                "details": parsed
            })
            state["steps"].append(step)
            state["parsed_query"] = parsed

        except Exception as e:
            step.update({
                "status": "error",
                "output": f"Query parsing failed: {str(e)}"
            })
            state["steps"].append(step)
            state["error"] = f"Query parsing failed: {str(e)}"
        return state

    def _find_provider(self, state: BookingState) -> BookingState:
        """Find nearest provider"""
        step = {
            "tool": "Distance Tool",
            "action": "Find nearest provider",
            "status": "running"
        }

        try:
            if state.get("error") or not state.get("parsed_query"):
                step.update({
                    "status": "failed",
                    "output": "Missing parsed query details"
                })
                state.setdefault("steps", []).append(step)
                return state

            query = state["parsed_query"]
            location = query.get("location") or "Business Bay"
            service = query.get("service") or "manicure"

            step["input"] = f"Service: {service}, Location: {location}"

            if not service:
                step.update({
                    "status": "failed",
                    "output": "No service detected in query"
                })
                state["steps"].append(step)
                state["error"] = "No service detected in query"
                return state

            providers = self.firestore_client.get_providers_by_service(service)
            if not providers:
                message = f"No providers found for {service}"
                step.update({
                    "status": "failed",
                    "output": message
                })
                state["steps"].append(step)
                state["error"] = message
                return state

            from geo import GeoService
            geo_service = GeoService()
            nearest = geo_service.find_nearest_providers(location, providers, limit=1)

            if nearest:
                provider = nearest[0]
                state["provider"] = provider
                step.update({
                    "status": "success",
                    "output": f"Found {provider.get('name')} at {provider.get('distance_km', 0):.1f}km from {location}",
                    "details": {
                        "provider_name": provider.get("name"),
                        "distance_km": provider.get("distance_km"),
                        "total_providers_checked": len(providers)
                    }
                })
            else:
                step.update({
                    "status": "failed",
                    "output": "No nearby providers found"
                })
                state["error"] = "No nearby providers found"

            state["steps"].append(step)

        except Exception as e:
            step.update({
                "status": "error",
                "output": f"Provider search failed: {str(e)}"
            })
            state.setdefault("steps", []).append(step)
            state["error"] = f"Provider search failed: {str(e)}"
        return state
    
    def _check_availability(self, state: BookingState) -> BookingState:
        """Check availability across multiple providers to ensure 3 slots"""
        step = {
            "tool": "Availability Tool",
            "action": "Check available time slots",
            "status": "running"
        }
        
        try:
            if state.get("error"):
                return state
            
            query = state["parsed_query"]
            service = query.get("service", "manicure")
            time_pref = query.get("preferred_time")
            location = query.get("location") or "Business Bay"
            normalized_time_pref = time_pref.strip().lower() if isinstance(time_pref, str) else None
            
            step["input"] = f"Service: {service}, Location: {location}, Time preference: {time_pref or 'any'}"
            
            # Get all providers for this service
            all_providers = self.firestore_client.get_providers_by_service(service)
            if not all_providers:
                step.update({
                    "status": "failed",
                    "output": f"No providers found for {service}"
                })
                state["steps"].append(step)
                state["error"] = f"No providers found for {service}"
                return state
            
            # Sort providers by distance from location
            from geo import GeoService
            geo_service = GeoService()
            sorted_providers = geo_service.find_nearest_providers(location, all_providers, limit=len(all_providers))
            full_sorted_providers = list(sorted_providers)
            
            # If budget is specified, prioritize cheaper providers based on actual service prices
            budget = query.get("budget")
            budget_preference = query.get("budget_preference", "")
            budget_mode_message = ""
            budget_mode_active = bool(budget) or budget_preference == "cheap"
            service_catalog = self.firestore_client.get_service_by_name(service)
            
            # Handle "cheap" keyword (budget = -1) or specific budget number
            if (budget and budget == -1) or budget_preference == "cheap":
                budget_mode_message = "💰 Budget mode: Looking for cheap/affordable options"
                print(budget_mode_message)
                # Sort providers by average pricing (need to check service prices)
                providers_with_prices = []
                for provider in sorted_providers:
                    # Get service price for this provider (check Firestore)
                    if not service_catalog:
                        continue
                    base_price = service_catalog.get("basePrice", 100)
                    # Apply 20% discount for budget providers (assumed cheaper tier)
                    if provider.get('name') in ['Elite Beauty Marina', 'Zen Wellness Karama', 'Bliss Spa Motor City', 'Glow Beauty Barsha', 'Prestige Salon Satwa']:
                        estimated_price = base_price * 0.8  # 20% cheaper
                    else:
                        estimated_price = base_price
                    providers_with_prices.append((provider, estimated_price))
                
                if providers_with_prices:
                    # Sort by price, then distance
                    providers_with_prices.sort(key=lambda x: (x[1], x[0].get('distance_km', 0)))
                    sorted_providers = [p[0] for p in providers_with_prices]
                    budget_mode_message += f" | Prioritized {len(sorted_providers)} providers by price"
                    print(f"💰 Prioritized {len(sorted_providers)} providers by affordability")
            
            elif budget and isinstance(budget, (int, float)) and budget > 0:
                budget_mode_message = f"💰 Budget mode: Looking for options under AED {budget}"
                print(budget_mode_message)
                
                # Provider pricing tiers (must match _filter_and_sort_by_budget)
                provider_pricing_tiers = {
                    'budget': ['Elite Beauty Marina', 'Zen Wellness Karama', 'Bliss Spa Motor City'],
                    'standard': ['Glamour Studio Business Bay', 'Wellness Hub Downtown', 'Divine Beauty Silicon Oasis'],
                    'premium': ['Serenity Spa JLT', 'Luxe Spa Jumeirah', 'Prestige Salon Satwa']
                }
                
                # Filter by specific budget with provider tier pricing
                providers_with_prices = []
                for provider in sorted_providers:
                    if not service_catalog:
                        continue
                    base_price = service_catalog.get("basePrice", 100)
                    provider_name = provider.get('name', '')
                    
                    # Apply provider tier multiplier
                    if provider_name in provider_pricing_tiers['budget']:
                        provider_multiplier = 0.5
                    elif provider_name in provider_pricing_tiers['premium']:
                        provider_multiplier = 1.3
                    else:
                        provider_multiplier = 1.0
                    
                    provider_price = base_price * provider_multiplier
                    total_price = provider_price * 1.05  # Add 5% tax
                    
                    if total_price <= budget:
                        providers_with_prices.append(provider)
                
                if providers_with_prices:
                    sorted_providers = providers_with_prices
                    budget_mode_message += f" | Found {len(sorted_providers)} providers within budget"
                    print(f"💰 Found {len(sorted_providers)} providers within budget AED {budget}")
                else:
                    # No providers within budget in this location
                    # Try to find budget-tier providers from other locations
                    budget_mode_message += " | No providers found within budget in this location"
                    print(f"💰 No providers within budget AED {budget}, searching budget-tier providers from other locations")
                    
                    # Get all providers for this service (not just nearby)
                    all_service_providers = all_providers
                    all_sorted = full_sorted_providers
                    
                    # Filter for budget-tier providers
                    budget_tier_providers = []
                    for provider in all_sorted:
                        if not service_catalog:
                            continue
                        base_price = service_catalog.get("basePrice", 100)
                        provider_name = provider.get('name', '')
                        
                        if provider_name in provider_pricing_tiers['budget']:
                            provider_multiplier = 0.5
                        elif provider_name in provider_pricing_tiers['premium']:
                            provider_multiplier = 1.3
                        else:
                            provider_multiplier = 1.0
                        
                        provider_price = base_price * provider_multiplier
                        total_price = provider_price * 1.05
                        
                        if total_price <= budget:
                            budget_tier_providers.append(provider)
                    
                    if budget_tier_providers:
                        sorted_providers = budget_tier_providers
                        budget_mode_message += f", found {len(budget_tier_providers)} budget providers in other areas"
                        print(f"💰 Found {len(budget_tier_providers)} budget-tier providers within budget from other locations")
                    else:
                        budget_mode_message += ", no providers available within budget"
                        print(f"💰 No providers available within budget AED {budget} even from other locations")
            
            # Collect candidate providers that have unbooked slots
            candidates = []
            providers_checked = 0
            ideal_candidate_found = False
            min_providers_before_break = 1 if not budget_mode_active else 3
            
            for provider in sorted_providers:
                providers_checked += 1
                
                provider_slots = self.firestore_client.get_available_slots(
                    provider_id=provider.get("provider_id"),
                    service_type=service,
                    date=query.get("preferred_date"),
                    include_booked=True
                )
                
                print(f"🔍 Provider '{provider.get('name')}': Found {len(provider_slots)} total slots")

                preferred_date = query.get("preferred_date")
                if preferred_date:
                    preferred_date_lower = preferred_date.lower()
                    is_next_week = "next" in preferred_date_lower
                    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
                    matched_weekday = next((day for day in weekdays if day in preferred_date_lower), None)

                    if matched_weekday:
                        date_filter = f"next_{matched_weekday}" if is_next_week else matched_weekday
                        provider_slots = self._filter_slots_by_specific_date(provider_slots, date_filter)
                    elif preferred_date_lower in ["today"]:
                        provider_slots = self._filter_slots_by_specific_date(provider_slots, "today")
                    elif preferred_date_lower in ["tomorrow"]:
                        provider_slots = self._filter_slots_by_specific_date(provider_slots, "tomorrow")

                for slot in provider_slots:
                    slot['provider_name'] = provider.get('name')
                    slot['provider_id'] = provider.get('provider_id')
                    slot['distance_km'] = provider.get('distance_km', 0)

                unbooked_slots = [s for s in provider_slots if not s.get('isBooked', False)]
                booked_slots = [s for s in provider_slots if s.get('isBooked', False)]

                print(f"   └─ Unbooked: {len(unbooked_slots)}, Booked: {len(booked_slots)}")

                if not unbooked_slots:
                    if provider_slots:
                        print(f"   ⚠️ All slots booked at '{provider.get('name')}', trying next provider...")
                    continue

                candidate_entry = {
                    "provider": provider,
                    "slots": provider_slots,
                    "unbooked": len(unbooked_slots)
                }

                if time_pref and time_pref != "any":
                    filtered_matches = self._filter_slots_by_time(provider_slots, time_pref)
                    candidate_entry["time_filtered"] = filtered_matches
                    candidate_entry["match_count"] = len(filtered_matches)
                else:
                    candidate_entry["time_filtered"] = provider_slots
                    candidate_entry["match_count"] = len(unbooked_slots)

                candidates.append(candidate_entry)

                if not budget_mode_active:
                    if normalized_time_pref and normalized_time_pref != "any":
                        if candidate_entry["match_count"] >= 3:
                            ideal_candidate_found = True
                    else:
                        if len(unbooked_slots) >= 3:
                            ideal_candidate_found = True

                if ideal_candidate_found and providers_checked >= min_providers_before_break:
                    print("✅ Early exit: found provider with sufficient matching slots")
                    break

            if not candidates:
                step.update({
                    "status": "failed",
                    "output": f"No available slots found for {service} in {location} on {query.get('preferred_date', 'any date')} at {time_pref} time"
                })
                state["steps"].append(step)
                state["error"] = f"No available slots found for your request. Please try a different date or time."
                return state

            best_provider = None
            selected_candidate = None
            time_filter_applied = False
            time_match_found = False

            def candidate_distance(candidate):
                provider_distance = candidate["provider"].get("distance_km")
                return provider_distance if isinstance(provider_distance, (int, float)) else float("inf")

            distance_cap = self._get_distance_cap(location)

            if time_pref and time_pref != "any":
                enriched_candidates = []
                for candidate in candidates:
                    filtered = candidate.get("time_filtered")
                    if filtered is None:
                        filtered = self._filter_slots_by_time(candidate["slots"], time_pref)
                    candidate["time_filtered"] = filtered
                    candidate["match_count"] = len(filtered)
                    enriched_candidates.append(candidate)

                def select_candidate(min_matches: int) -> Optional[Dict[str, Any]]:
                    pool = [c for c in enriched_candidates if c.get("match_count", 0) >= min_matches]
                    if not pool:
                        return None
                    if distance_cap is not None:
                        within_cap = [c for c in pool if candidate_distance(c) <= distance_cap]
                        if within_cap:
                            pool = within_cap
                    return min(
                        pool,
                        key=lambda c: (
                            -c.get("match_count", 0),
                            candidate_distance(c)
                        )
                    )

                selected_candidate = select_candidate(2)
                if not selected_candidate:
                    selected_candidate = select_candidate(1)

                if not selected_candidate:
                    pool = enriched_candidates
                    if distance_cap is not None:
                        within_cap = [c for c in pool if candidate_distance(c) <= distance_cap]
                        if within_cap:
                            pool = within_cap
                    selected_candidate = min(pool, key=candidate_distance)

                time_filter_applied = True
                time_match_found = selected_candidate.get("match_count", 0) > 0
            else:
                selected_candidate = min(candidates, key=candidate_distance)
                selected_candidate["time_filtered"] = selected_candidate["slots"]
                selected_candidate["match_count"] = len(selected_candidate["slots"])

            best_provider = selected_candidate["provider"]
            all_slots = selected_candidate["slots"]
            initial_slot_count = len(all_slots)

            if time_pref and time_pref != "any":
                filtered_slots = selected_candidate.get("time_filtered", [])
            else:
                filtered_slots = all_slots

            if time_pref and time_pref != "any" and not filtered_slots:
                provider_name = best_provider.get('name') if best_provider else 'unknown'
                print(f"⚠️ No slots match '{time_pref}' from provider '{provider_name}', falling back to nearest alternatives")
                filtered_slots = all_slots
            
            # Filter by budget if specified
            budget = query.get("budget")
            budget_alternative = False
            original_service = service
            
            if budget and isinstance(budget, (int, float)) and budget > 0:
                # Apply budget-aware provider filtering
                affordable_slots = self._filter_and_sort_by_budget(filtered_slots, budget, service)
                
                if affordable_slots:
                    filtered_slots = affordable_slots
                    print(f"💰 Budget filter: Found {len(filtered_slots)} slots under AED {budget}")
                    # Update best_provider to match the provider of the filtered slots
                    if filtered_slots and 'provider_id' in filtered_slots[0]:
                        provider_id = filtered_slots[0]['provider_id']
                        # Find matching provider from sorted_providers
                        for provider in sorted_providers:
                            if provider.get('provider_id') == provider_id:
                                best_provider = provider
                                print(f"💰 Updated provider to budget-compliant: {provider.get('name')}")
                                break
                else:
                    print(f"💰 No slots found under AED {budget} for {service}")
                    # Keep original slots but inform user about pricing
                    filtered_slots = self._sort_slots_by_distance_and_price(filtered_slots)
            else:
                # No budget specified, sort by distance and price
                filtered_slots = self._sort_slots_by_distance_and_price(filtered_slots)
            
            # ALWAYS return 3 slots - pad with booked slots if needed
            final_slots = filtered_slots[:3]  # Top 3 slots
            
            # If we have less than 3 slots, we already fetched all slots (including booked)
            # The include_booked=True should have given us more, but if still < 3, use what we have
            if len(final_slots) < 3:
                print(f"⚠️ Only {len(final_slots)} slot(s) available after filtering, returning what we have")
            
            state["available_slots"] = final_slots
            
            # Set the provider (use best provider with slots)
            if best_provider:
                state["provider"] = best_provider
            
            # Create step output
            output_parts = []
            
            # Add budget mode info if active
            if budget_mode_message:
                output_parts.append(budget_mode_message)
            
            output_parts.append(f"Found {initial_slot_count} total slots for {original_service}")
            if providers_checked > 1:
                output_parts.append(f"checked {providers_checked} providers")
            if time_filter_applied:
                output_parts.append(f"filtered to {len(filtered_slots)} for {time_pref} preference")
                if distance_cap is not None:
                    provider_distance = candidate_distance(selected_candidate)
                    if provider_distance > distance_cap:
                        output_parts.append(f"closest match beyond {distance_cap}km (selected {provider_distance:.1f}km)")
                    else:
                        output_parts.append(f"kept provider within {distance_cap}km radius")
            if budget_alternative:
                output_parts.append(f"switched to budget-friendly service: {query['service']} (within AED {budget} budget)")
            output_parts.append(f"returning top {len(final_slots)} slots")
            
            step.update({
                "status": "success",
                "output": ", ".join(output_parts),
                "details": {
                    "initial_slots": initial_slot_count,
                    "filtered_slots": len(filtered_slots),
                    "final_slots": len(final_slots),
                    "providers_checked": providers_checked,
                    "time_filter_applied": time_filter_applied,
                    "budget_alternative": budget_alternative,
                    "budget_mode_active": bool(budget_mode_message)
                }
            })
            state["steps"].append(step)
            
        except Exception as e:
            step.update({
                "status": "error",
                "output": f"Availability check failed: {str(e)}"
            })
            state["steps"].append(step)
            state["error"] = f"Availability check failed: {str(e)}"
        return state
    
    def _calculate_pricing(self, state: BookingState) -> BookingState:
        """Calculate pricing"""
        step = {
            "tool": "Pricing Tool",
            "action": "Calculate service pricing",
            "status": "running"
        }
        
        try:
            if state.get("error"):
                return state
            
            query = state["parsed_query"]
            service = query.get("service", "manicure")
            
            step["input"] = f"Service: {service}"
            
            service_catalog = self.firestore_client.get_service_by_name(service)
            available_slots = state.get("available_slots", [])

            baseline_subtotal = None
            provider_tier = None
            slot_total = None
            allow_discount = False

            if query.get("budget") or query.get("budget_preference") in {"cheap", "budget"}:
                allow_discount = True

            if service_catalog and isinstance(service_catalog.get("basePrice"), (int, float)):
                baseline_subtotal = float(service_catalog["basePrice"])

            if available_slots:
                first_slot = available_slots[0]
                provider_tier = first_slot.get("provider_tier", "Standard")
                if isinstance(provider_tier, str) and provider_tier.lower() == "budget":
                    allow_discount = True
                if isinstance(first_slot.get("base_price"), (int, float)) and first_slot["base_price"] > 0:
                    inferred_base = float(first_slot["base_price"])
                    if baseline_subtotal is None or inferred_base > baseline_subtotal:
                        baseline_subtotal = inferred_base
                if isinstance(first_slot.get("calculated_price"), (int, float)) and first_slot["calculated_price"] > 0:
                    slot_total = float(first_slot["calculated_price"])

            if baseline_subtotal is None:
                baseline_subtotal = 100.0

            baseline_total = round(baseline_subtotal * 1.05, 2)

            if slot_total and (slot_total > baseline_total or allow_discount):
                total_price = round(slot_total, 2)
                subtotal = round(total_price / 1.05, 2)
            else:
                total_price = baseline_total
                subtotal = round(baseline_subtotal, 2)

            tax = round(total_price - subtotal, 2)

            pricing = {
                "service_name": service_catalog.get("name", service.title()) if service_catalog else service.title(),
                "base_price": round(subtotal, 2),
                "subtotal": round(subtotal, 2),
                "tax": tax,
                "total_price": total_price,
                "currency": "AED"
            }

            if provider_tier:
                pricing["provider_tier"] = provider_tier

            step.update({
                "status": "success",
                "output": f"Base: AED {pricing['base_price']}, Tax: AED {tax}, Total: AED {total_price}"
                          + (f" ({provider_tier} provider)" if provider_tier else ""),
                "details": pricing
            })
            
            state["pricing"] = pricing
            state["steps"].append(step)
                
        except Exception as e:
            step.update({
                "status": "error",
                "output": f"Pricing calculation failed: {str(e)}"
            })
            state["steps"].append(step)
            state["error"] = f"Pricing calculation failed: {str(e)}"
        return state
    
    def _create_proposal(self, state: BookingState) -> BookingState:
        """Create booking proposal"""
        try:
            if state.get("error"):
                return state
            
            provider = state.get("provider", {})
            slots = state.get("available_slots", [])
            pricing = state.get("pricing", {})
            
            # Format distance
            distance_km = provider.get("distance_km", 0)
            if distance_km < 1:
                distance_text = f"{int(distance_km * 1000)}m"
            else:
                distance_text = f"{distance_km:.1f}km"
            
            proposal = {
                "provider": {
                    "name": provider.get("name", "Beauty Center"),
                    "location": provider.get("address", "Dubai"),  # Use full address
                    "phone": provider.get("phone", ""),
                    "rating": provider.get("rating", 0),
                    "distance": distance_text,
                    "distance_km": distance_km
                },
                "service": pricing.get("service_name", "Service"),
                "available_slots": slots,
                "pricing": pricing,
                "currency": "AED",
                "location": state["parsed_query"].get("location", "Dubai")
            }
            
            state["proposal"] = proposal
            
        except Exception as e:
            state["error"] = f"Proposal creation failed: {str(e)}"
        return state
    
    def _finalize_booking(self, state: BookingState) -> BookingState:
        """Finalize booking (save to database)"""
        try:
            if state.get("error") or not state.get("proposal"):
                return state
            
            proposal = state["proposal"]
            provider = proposal["provider"]
            slots = proposal["available_slots"]
            
            if not slots:
                state["error"] = "No available slots to book"
                return state
            
            # Create booking document
            booking_data = {
                "uid": state["uid"],
                "provider_id": state["provider"].get("id"),
                "provider_name": provider["name"],
                "service_name": proposal["service"],
                "slot": slots[0],  # Book first available slot
                "total_price": proposal["pricing"]["total_price"],
                "currency": proposal["currency"],
                "status": "confirmed",
                "created_at": datetime.now(timezone.utc),
                "location": proposal["location"]
            }
            
            # Save to Firestore
            booking_result = self.firestore_client.create_booking(
                uid=state["uid"],
                booking_data=booking_data
            )
            
            # Send email notification
            try:
                user_info = self.firestore_client.get_user(state["uid"])
                if user_info and user_info.get("email"):
                    from notification import EmailNotificationService
                    email_service = EmailNotificationService()
                    
                    # Prepare booking details for email
                    email_booking_details = {
                        "booking_id": booking_result.get("booking_id"),
                        "service": proposal["service"],
                        "provider": provider,
                        "selected_slot": slots[0] if slots else {},
                        "pricing": proposal["pricing"],
                        "user_preferences": state["parsed_query"]
                    }
                    
                    email_result = email_service.send_booking_confirmation(
                        user_email=user_info["email"],
                        booking_details=email_booking_details
                    )
                    
                    if email_result.get("success"):
                        booking_result["email_sent"] = True
                        booking_result["calendar_link"] = email_result.get("calendar_link")
                    else:
                        print(f"Email notification failed: {email_result.get('error')}")
                        
            except Exception as email_error:
                print(f"Email notification error: {email_error}")
                # Don't fail the booking if email fails
            
            state["booking_result"] = {
                "booking_id": booking_result.get("booking_id"),
                "status": "confirmed",
                "message": f"Booking confirmed at {provider['name']}",
                "email_sent": booking_result.get("email_sent", False),
                "calendar_link": booking_result.get("calendar_link")
            }
            
        except Exception as e:
            state["error"] = f"Booking creation failed: {str(e)}"
        return state
    
    def _get_distance_cap(self, location: Optional[str]) -> Optional[float]:
        """Return a reasonable distance cap (km) based on the requested location."""
        if not location:
            return None

        normalized = location.strip().lower()
        dense_hubs = {
            "business bay",
            "downtown",
            "downtown dubai",
            "difc",
            "al barsha",
            "jlt",
            "jumeirah lake towers",
            "dubai marina",
            "marina",
            "satwa",
            "karama",
            "deira",
        }

        suburban_hubs = {
            "mirdif",
            "silicon oasis",
            "academic city",
            "motor city",
            "arabian ranches",
            "dubai south",
        }

        if normalized in dense_hubs:
            return 12.0
        if normalized in suburban_hubs:
            return 18.0

        return 15.0

    def _filter_slots_by_time(self, slots: List[Dict], time_pref: str) -> List[Dict]:
        """
        Enhanced filter slots by time preference with smart fallback logic
        Supports specific time queries like "after 6 PM" and fallback to next appropriate slots
        Never returns after-midnight slots (restricts to 6 AM - 10 PM)
        """
        if not time_pref or time_pref == "any":
            # Even for "any", filter out unreasonable hours
            reasonable_slots = []
            for slot in slots:
                try:
                    start_time = self._parse_datetime_robust(slot.get("start"))
                    if start_time and 6 <= start_time.hour < 22:
                        reasonable_slots.append(slot)
                except Exception:
                    continue
            return reasonable_slots[:3] if reasonable_slots else slots[:3]
        
        filtered = []
        reasonable_hours_slots = []

        # Parse specific time patterns (after/before/around/exact hour)
        specific_time_match = self._parse_specific_time(time_pref)
        approx_matches: List[Tuple[int, Dict]] = []  # (minute_diff, slot)
        approx_window: Optional[Tuple[int, int]] = None
        target_minutes: Optional[int] = None

        if specific_time_match and specific_time_match.get("type") == "around":
            target_hour = specific_time_match.get("hour", 0)
            target_minute = specific_time_match.get("minute", 0)
            target_minutes = target_hour * 60 + target_minute
            window_start = max(6, target_hour - 1)
            window_end = min(22, target_hour + 2)
            approx_window = (window_start, window_end)

        for slot in slots:
            try:
                start_time = self._parse_datetime_robust(slot.get("start"))
                
                if not start_time:
                    continue
                
                local_time = start_time.astimezone(DUBAI_TZ)
                hour = local_time.hour
                
                # Filter out after-midnight and very early morning slots (10 PM - 6 AM)
                is_reasonable_hour = 6 <= hour < 22
                
                if is_reasonable_hour:
                    reasonable_hours_slots.append((slot, local_time, hour))
                
                # Handle specific time queries
                if specific_time_match:
                    match_type = specific_time_match.get("type")

                    if match_type == "comparison":
                        target_hour = specific_time_match.get("hour", 0)
                        operator = specific_time_match.get("operator")
                        if operator == "after" and hour >= target_hour and hour < 22:
                            filtered.append(slot)
                        elif operator == "before" and hour <= target_hour and hour >= 6:
                            filtered.append(slot)
                        continue

                    if match_type == "around" and approx_window and target_minutes is not None:
                        window_start, window_end = approx_window
                        if window_start <= hour < window_end:
                            minutes_since_midnight = hour * 60 + local_time.minute
                            minute_diff = abs(minutes_since_midnight - target_minutes)
                            approx_matches.append((minute_diff, slot))
                        continue
                    
                    if match_type == "exact":
                        target_hour = specific_time_match.get("hour", 0)
                        target_minute = specific_time_match.get("minute", 0)
                        if hour == target_hour and local_time.minute == target_minute:
                            filtered.append(slot)
                        continue
                
                # Standard time preference matching (stricter boundaries)
                if time_pref.lower() in ["morning", "am"] and 6 <= hour < 12:
                    filtered.append(slot)
                elif time_pref.lower() in ["afternoon", "pm"] and 12 <= hour < 18:
                    filtered.append(slot)
                elif time_pref.lower() in ["evening", "night"] and 18 <= hour < 22:  # Cap evening at 10 PM
                    filtered.append(slot)
                    
            except Exception:
                continue
        
        # Strict time enforcement: prefer exact/around matches
        if specific_time_match and specific_time_match.get("type") == "around" and approx_matches:
            approx_matches.sort(key=lambda item: item[0])
            return [slot for _, slot in approx_matches[:3]]

        if filtered:
            return filtered[:3]

        # No fallback to different time ranges - return empty to try another provider
        return []

    def _parse_specific_time(self, time_pref: str) -> Optional[Dict[str, Any]]:
        """Parse specific time queries (after, before, around, exact hour expressions)."""
        import re

        text = time_pref.lower()

        def normalize(hour_str: str, minute_str: Optional[str], period: Optional[str]) -> Tuple[int, int]:
            hour = int(hour_str)
            minute = int(minute_str) if minute_str else 0
            if period:
                if period == "pm" and hour != 12:
                    hour += 12
                elif period == "am" and hour == 12:
                    hour = 0
            return hour, minute

        around_pattern = r"(around|about|approximately|approx|near|close to)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
        match = re.search(around_pattern, text)
        if match:
            hour, minute = normalize(match.group(2), match.group(3), match.group(4))
            return {"type": "around", "hour": hour, "minute": minute}

        comparison_pattern = r"(after|before)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
        match = re.search(comparison_pattern, text)
        if match:
            hour, minute = normalize(match.group(2), match.group(3), match.group(4))
            return {"type": "comparison", "operator": match.group(1), "hour": hour, "minute": minute}

        explicit_ampm = r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b"
        match = re.search(explicit_ampm, text)
        if match:
            hour, minute = normalize(match.group(1), match.group(2), match.group(3))
            return {"type": "around", "hour": hour, "minute": minute}

        twenty_four_pattern = r"\b(\d{1,2}):(\d{2})\b"
        match = re.search(twenty_four_pattern, text)
        if match:
            hour, minute = normalize(match.group(1), match.group(2), None)
            return {"type": "exact", "hour": hour, "minute": minute}

        return None
    
    def _filter_slots_by_specific_date(self, slots: List[Dict], date_type: str) -> List[Dict]:
        """Filter slots by specific date (today, tomorrow, friday, next_friday, etc.)"""
        from datetime import datetime, timedelta
        
        today = datetime.now()
        
        if date_type == "today":
            target_date = today
        elif date_type == "tomorrow":
            target_date = today + timedelta(days=1)
        elif date_type.startswith("next_"):
            # Handle "next_friday", "next_monday", etc.
            weekday_name = date_type.replace("next_", "")
            weekday_map = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            
            if weekday_name in weekday_map:
                target_weekday = weekday_map[weekday_name]
                days_until_target = (target_weekday - today.weekday()) % 7
                
                # "next_X" always means NEXT occurrence, even if today is that day
                if days_until_target == 0:
                    # Today is that day, so "next" means 7 days ahead
                    target_date = today + timedelta(days=7)
                else:
                    target_date = today + timedelta(days=days_until_target)
            else:
                return slots  # Unknown weekday
        elif date_type in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            # Map weekday names to numbers (0=Monday, 6=Sunday)
            weekday_map = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6
            }
            target_weekday = weekday_map[date_type]
            days_until_target = (target_weekday - today.weekday()) % 7
            
            if days_until_target == 0:  # Today is the requested day
                target_date = today
            else:
                target_date = today + timedelta(days=days_until_target)
        else:
            return slots  # No filtering
        
        filtered = []
        target_date_str = target_date.strftime('%Y-%m-%d')
        
        for slot in slots:
            try:
                start_time = slot.get('start')
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                
                slot_date_str = start_time.strftime('%Y-%m-%d')
                if slot_date_str == target_date_str:
                    filtered.append(slot)
                    
            except Exception:
                continue
                
        return filtered if filtered else slots
    
    def _find_affordable_services(self, budget: float) -> List[Dict[str, Any]]:
        """Find services within budget"""
        try:
            all_services = self.firestore_client.get_all_services()
            affordable = []
            
            for service in all_services:
                base_price = service.get("basePrice", 100)
                total_price = base_price * 1.05  # Include 5% tax
                
                if total_price <= budget:
                    affordable.append(service)
            
            # Sort by price (cheapest first)
            affordable.sort(key=lambda x: x.get("basePrice", 100))
            return affordable
            
        except Exception as e:
            print(f"Error finding affordable services: {e}")
            return []
    
    def _check_for_error(self, state: BookingState) -> str:
        """Check if there's an error and decide workflow direction"""
        return "error" if state.get("error") else "continue"
    
    def _should_confirm(self, state: BookingState) -> str:
        """Check if booking should be confirmed"""
        return "confirm" if state.get("confirm", False) else "end"
    
    def process_booking_request(self, uid: str, query: str, confirm: bool = False) -> Dict[str, Any]:
        """Main entry point for booking requests"""
        
        initial_state = BookingState(
            query=query,
            uid=uid,
            confirm=confirm,
            parsed_query=None,
            provider=None,
            available_slots=None,
            pricing=None,
            proposal=None,
            booking_result=None,
            error=None,
            steps=[]
        )
        
        try:
            final_state = self.workflow.invoke(initial_state)
            
            if final_state.get("error"):
                return {
                    "success": False,
                    "error": final_state["error"],
                    "steps": final_state.get("steps", [])
                }
            
            return {
                "success": True,
                "proposal": final_state.get("proposal"),
                "booking_result": final_state.get("booking_result"),
                "available_slots": final_state.get("available_slots"),
                "provider": final_state.get("provider"),
                "pricing": final_state.get("pricing"),
                "parsed_query": final_state.get("parsed_query"),
                "steps": final_state.get("steps", [])
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Workflow execution failed: {str(e)}"
            }
    
    def _parse_datetime_robust(self, date_string):
        """
        Robust datetime parser that handles multiple formats:
        - ISO format: "2025-10-02T17:00:00+00:00" or "2025-10-02T17:00:00Z"
        - GMT format: "Thu, 02 Oct 2025 17:00:00 GMT"
        """
        if not date_string:
            return None
        
        import re
        
        # Handle GMT format first (the actual problem)
        if 'GMT' in str(date_string):
            try:
                # Parse format like "Thu, 02 Oct 2025 17:00:00 GMT"
                cleaned = re.sub(r'^[A-Za-z]+,\s*', '', str(date_string))  # Remove "Thu, "
                cleaned = cleaned.replace(' GMT', '')  # Remove " GMT"
                
                # Parse the remaining: "02 Oct 2025 17:00:00"
                dt = datetime.strptime(cleaned, '%d %b %Y %H:%M:%S')
                
                # Add UTC timezone info
                dt = dt.replace(tzinfo=timezone.utc)
                return dt
                
            except Exception as e:
                print(f"GMT parsing failed for '{date_string}': {e}")
                return None
        
        # Handle ISO format (current expectation)
        elif 'T' in str(date_string):
            try:
                return datetime.fromisoformat(str(date_string).replace('Z', '+00:00'))
            except Exception as e:
                print(f"ISO parsing failed for '{date_string}': {e}")
                return None
        
        # Handle datetime objects
        elif isinstance(date_string, datetime):
            return date_string
            
        else:
            print(f"Unknown datetime format: '{date_string}'")
            return None

    def get_user_bookings(self, uid: str) -> List[Dict[str, Any]]:
        """Get user booking history"""
        try:
            return self.firestore_client.get_user_bookings(uid)
        except Exception as e:
            print(f"Error getting bookings: {e}")
            return []
    
    def _remove_duplicate_slots(self, slots):
        """Remove duplicate slots based on start time and service"""
        seen_slots = set()
        unique_slots = []
        
        for slot in slots:
            # Create unique identifier
            start_time = slot.get('start', slot.get('start_time', ''))
            service = slot.get('serviceName', slot.get('service', ''))
            
            # Convert datetime to string for comparison
            if hasattr(start_time, 'isoformat'):
                time_str = start_time.isoformat()
            else:
                time_str = str(start_time)
            
            unique_key = f"{time_str}_{service}"
            
            if unique_key not in seen_slots:
                seen_slots.add(unique_key)
                unique_slots.append(slot)
            
        return unique_slots

    def check_availability(self, service_name: str, provider: Dict[str, Any], date_filter: str = None, time_pref: str = None) -> str:
        """Check availability with duplicate removal"""
        try:
            print(f"🔍 Checking availability for {service_name} at {provider.get('name', 'Unknown Provider')}")
            
            # Get slots from database
            slots = self.firestore.get_available_slots(provider.get('id'), service_name, date_filter)
            print(f"📊 Found {len(slots)} total slots")
            
            if not slots:
                return f"No slots available for {service_name}"
            
            # Remove duplicates first
            unique_slots = self._remove_duplicate_slots(slots)
            print(f"🔧 After removing duplicates: {len(unique_slots)} unique slots")
            
            # Apply date filtering if specified
            if date_filter:
                date_filtered_slots = self._filter_slots_by_specific_date(unique_slots, date_filter)
                print(f"📅 Date filtering: {len(unique_slots)} -> {len(date_filtered_slots)} slots for {date_filter}")
            else:
                date_filtered_slots = unique_slots
            
            # Apply time filtering if specified
            if time_pref:
                time_filtered_slots = self._filter_slots_by_time(date_filtered_slots, time_pref)
                print(f"⏰ Time filtering: {len(date_filtered_slots)} -> {len(time_filtered_slots)} slots for {time_pref}")
                filtered_slots = time_filtered_slots
            else:
                filtered_slots = date_filtered_slots
            
            # Return top 3 unique slots
            final_slots = filtered_slots[:3]
            print(f"🎯 Returning top {len(final_slots)} unique slots")
            
            if final_slots:
                slots_info = []
                for slot in final_slots:
                    start_time = slot.get('start', slot.get('start_time'))
                    service = slot.get('serviceName', slot.get('service'))
                    
                    if start_time:
                        if hasattr(start_time, 'strftime'):
                            time_display = start_time.strftime('%a, %b %d at %I:%M %p')
                        else:
                            time_display = str(start_time)
                        slots_info.append(f"{time_display} - {service}")
                
                return f"Found {len(filtered_slots)} total slots for {service_name}, filtered to {len(final_slots)} for {time_pref or 'all times'}, returning top {len(final_slots)} slots: " + "; ".join(slots_info)
            else:
                # Fallback: return next 3 available slots if no matches
                fallback_slots = self._remove_duplicate_slots(unique_slots[:3])
                print(f"🔄 No slots found for '{time_pref or date_filter}', returning next {len(fallback_slots)} unique available slots")
                
                if fallback_slots:
                    slots_info = []
                    for slot in fallback_slots:
                        start_time = slot.get('start', slot.get('start_time'))
                        service = slot.get('serviceName', slot.get('service'))
                        
                        if start_time:
                            if hasattr(start_time, 'strftime'):
                                time_display = start_time.strftime('%a, %b %d at %I:%M %p')
                            else:
                                time_display = str(start_time)
                            slots_info.append(f"{time_display} - {service}")
                    
                    return f"No slots found for '{time_pref or date_filter}', returning next {len(fallback_slots)} unique available slots: " + "; ".join(slots_info)
                else:
                    return f"No slots available for {service_name}"
        
        except Exception as e:
            print(f"❌ Error checking availability: {e}")
            return f"Error checking availability: {str(e)}"
    
    def _filter_and_sort_by_budget(self, slots: List[Dict], budget: float, service: str) -> List[Dict]:
        """Filter and sort slots by budget using provider-specific pricing"""
        affordable_slots = []
        
        # Get base service price
        service_data = self.firestore_client.get_service_by_name(service)
        if not service_data:
            return []
        
        base_price = service_data.get("basePrice", 100)
        
        # Provider pricing tiers (some providers are cheaper/more expensive)
        provider_pricing_tiers = {
            # Budget-friendly providers (40% discount for affordability)
            'budget': ['Elite Beauty Marina', 'Zen Wellness Karama', 'Bliss Spa Motor City'],
            # Standard providers (base price)
            'standard': ['Glamour Studio Business Bay', 'Wellness Hub Downtown', 'Divine Beauty Silicon Oasis'],
            # Premium providers (30% markup)
            'premium': ['Serenity Spa JLT', 'Luxe Spa Jumeirah', 'Prestige Salon Satwa']
        }
        
        for slot in slots:
            try:
                provider_name = slot.get('provider_name', '')
                if not provider_name:
                    continue
                
                # Determine provider tier and calculate price
                if provider_name in provider_pricing_tiers['budget']:
                    provider_multiplier = 0.5  # 50% discount for budget providers
                elif provider_name in provider_pricing_tiers['premium']:
                    provider_multiplier = 1.3  # 30% markup
                else:
                    provider_multiplier = 1.0  # Standard price
                
                # Calculate final price with tax
                provider_price = base_price * provider_multiplier
                total_price = provider_price * 1.05  # Add 5% tax
                
                # Add price info to slot
                slot['calculated_price'] = total_price
                slot['base_price'] = provider_price
                slot['provider_tier'] = (
                    'Budget' if provider_multiplier == 0.5 else
                    'Premium' if provider_multiplier == 1.3 else 'Standard'
                )
                
                # Check if within budget
                if total_price <= budget:
                    affordable_slots.append(slot)
                    
            except Exception as e:
                print(f"Error processing slot budget: {e}")
                continue
        
        # Sort affordable slots by price (cheapest first), then by distance
        affordable_slots.sort(key=lambda x: (
            x.get('calculated_price', 999),
            x.get('distance_km', 999)
        ))
        
        return affordable_slots
    
    def _sort_slots_by_price(self, slots: List[Dict]) -> List[Dict]:
        """Sort slots by price (cheapest first), then by distance"""
        try:
            # Ensure all slots have price information
            for slot in slots:
                if 'calculated_price' not in slot:
                    service_name = slot.get('serviceName', '')
                    service_data = self.firestore_client.get_service_by_name(service_name)
                    if service_data:
                        base_price = service_data.get("basePrice", 100)
                        slot['calculated_price'] = base_price * 1.05
                        slot['base_price'] = base_price
                    else:
                        slot['calculated_price'] = 105  # Default fallback
                        slot['base_price'] = 100
            
            # Sort by price first, then by distance
            sorted_slots = sorted(slots, key=lambda x: (
                x.get('calculated_price', 105),
                x.get('distance_km', 999)
            ))
            
            return sorted_slots
            
        except Exception as e:
            print(f"Error sorting slots by price: {e}")
            return slots
    
    def _sort_slots_by_distance_and_price(self, slots: List[Dict]) -> List[Dict]:
        """Sort slots: unbooked first, then booked (sorted by distance and price)"""
        try:
            # Ensure all slots have price information
            for slot in slots:
                if 'calculated_price' not in slot:
                    service_name = slot.get('serviceName', '')
                    service_data = self.firestore_client.get_service_by_name(service_name)
                    if service_data:
                        base_price = service_data.get("basePrice", 100)
                        slot['calculated_price'] = base_price * 1.05
                        slot['base_price'] = base_price
                    else:
                        slot['calculated_price'] = 105  # Default fallback
                        slot['base_price'] = 100
            
            # ✅ Sort: UNBOOKED FIRST (isBooked=False), then BOOKED (isBooked=True)
            # Within each group, sort by distance, then by price
            sorted_slots = sorted(slots, key=lambda x: (
                x.get('isBooked', False),  # Unbooked (False) comes before Booked (True)
                x.get('distance_km', 999),
                x.get('calculated_price', 105)
            ))
            
            return sorted_slots
            
        except Exception as e:
            print(f"Error sorting slots by distance and price: {e}")
            return slots