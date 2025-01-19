from channels.generic.websocket import AsyncWebsocketConsumer
import json

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """
        Called when the WebSocket connection is established.
        Simply accepts the connection - no groups needed for single player.
        """
        self.game_id = self.scope['url_route']['kwargs']['game_id']
        await self.accept()
        
    async def disconnect(self, close_code):
        """
        Called when the WEbSocket closes.
        """
        pass  # No cleanup needed for single player
    
    async def receive(self, text_data):
        """
        Handles incoming messages from the client.
        """
        try:
            data = json.loads(text_data)
            event_type = data.get('type')
            
            if event_type == 'submit_answer':
                #Process the answer and send back result
                answer = data.get('answer')
                # You would implement your answer validation logic here
                #for example:
                result = self.validate_answer(answer)
                
                await self.send(text_data=json.dumps({
                    "type": 'answer_result',
                    'correct': result['correct'],
                    'score': result['score'],
                    'feedback': result['feedback']
                }))
                
            elif event_type == 'request_hint':
                # Process hint request
                hint = self.get_hint()
                await self.send(text_data=json.dumps({
                    'type': 'hint_response',
                    'hint': hint
                }))
                
            elif event_type == 'game_state':
                # Send current game state
                game_state = self.get_game_state()
                await self.send(text_data=json.dumps({
                    'type': 'game_state_update',
                    'state': game_state
                }))
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid message format'
            }))
            
    def validate_answer(self, answer):
        """
        Placeholder for answer validation logic.
        You would implement your actual game logic here.
        """
        
        # This is where you'd implement your actual validation logic
        return {
            'correct': False,
            'score': 0,
            'feedback': 'Answer validation not implemented'
        }
        
    def get_hint(self):
        """
        Placeholder for game state retrieval logic.
        """
        return {
            'status': 'active',
            'current_level': 1,
            'score': 0
        }
        
            