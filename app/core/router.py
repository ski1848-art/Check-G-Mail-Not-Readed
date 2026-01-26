from typing import List, Set, Optional
from app.models import GmailEvent, NotificationTarget
from app.config import Config
from app.utils.logger import get_logger
from app.services.routing_store import RoutingStore

logger = get_logger("router")

class Router:
    def __init__(self):
        self.routing_rules = []
        if Config.ROUTING_SOURCE == "json":
            self.routing_rules = Config.load_routing_rules()
        self.routing_store = RoutingStore()
        
    def get_targets(self, event: GmailEvent) -> List[NotificationTarget]:
        """
        Determine Slack notification targets based on email recipients.
        """
        targets_set: Set[NotificationTarget] = set()
        
        # Collect all emails involved (recipients + owner as potential recipient)
        involved_emails = set(event.recipients)
        involved_emails.add(event.owner)
        
        logger.info(f"Routing for emails: {involved_emails}")
        
        if Config.ROUTING_SOURCE == "firestore":
            try:
                for email in involved_emails:
                    targets = self.routing_store.get_targets_for_gmail(email)
                    for t in targets:
                        targets_set.add(t)
                
                # If no targets found via firestore and we want to fallback to json
                if not targets_set:
                    logger.debug("No targets found in Firestore, checking JSON fallback if available.")
                    self._add_targets_from_json(involved_emails, targets_set)
                    
            except Exception as e:
                logger.error(f"Firestore routing failed: {e}. Falling back to JSON.")
                self._add_targets_from_json(involved_emails, targets_set)
        else:
            self._add_targets_from_json(involved_emails, targets_set)
                    
        targets_list = list(targets_set)
        logger.info(f"Final routing: {len(targets_list)} unique targets")
        
        return targets_list

    def _add_targets_from_json(self, involved_emails: Set[str], targets_set: Set[NotificationTarget]):
        """Helper to add targets from static JSON config."""
        # Reload if empty and source is json, or just use what's loaded
        rules = self.routing_rules if self.routing_rules else Config.load_routing_rules()
        
        for email in involved_emails:
            for rule in rules:
                if rule.get("email") == email:
                    rule_targets = rule.get("targets", [])
                    for target_str in rule_targets:
                        target = self._parse_target(target_str)
                        if target:
                            targets_set.add(target)
                    logger.info(f"Matched JSON rule for {email}: {len(rule_targets)} targets")
    
    def _parse_target(self, target_str: str) -> Optional[NotificationTarget]:
        """
        Parse target string format.
        Expected formats:
        - "user:U12345" -> Slack User ID
        - "channel:#channel-name" -> Channel name
        - "channel:C12345" -> Channel ID
        """
        try:
            if target_str.startswith("user:"):
                user_id = target_str.replace("user:", "")
                return NotificationTarget(target_id=user_id, target_type="user")
                
            elif target_str.startswith("channel:"):
                channel_id = target_str.replace("channel:", "")
                return NotificationTarget(target_id=channel_id, target_type="channel")
                
            else:
                logger.warning(f"Unknown target format: {target_str}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to parse target {target_str}: {e}")
            return None

