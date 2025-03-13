from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions
import logging

logger = logging.getLogger('spotify')
    
class JWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        logger.debug("Attempting authentication")
        header = self.get_header(request)
        if header is None:
            logger.debug("No header found")
            return None
            

        logger.debug(f"Header: {header}")
        try:
            prefix = self.get_raw_token(header)
            if prefix is None:
                logger.debug("No prefix found")
                return None

            validated_token = self.get_validated_token(prefix)
            logger.debug(f"Successfully authenticated user {validated_token.user.id}, {validated_token}")
            user = self.get_user(validated_token)
            return (user, validated_token)
        except Exception:
            return None