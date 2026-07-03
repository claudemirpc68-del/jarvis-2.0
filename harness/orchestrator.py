import os
import json
from datetime import datetime
from pathlib import Path
import httpx

from harness.logger import logger
from harness.memory import JarvisMemory
from harness.security import JarvisSecurity
from config import config

# Importar a única ferramenta necessária
import tools.customer_sheets_tool as customer_sheets

class JarvisOrchestrator:
    def __init__(self):
        self.memory = JarvisMemory()
        self.security = JarvisSecurity()
        self.groq_api_key = config.api.groq_api_key or os.environ.get("GROQ_API_KEY", "")
        self.openrouter_api_key = config.api.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.gemini_api_key = config.api.gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        
        # Caminho absoluto para o system prompt
        self.prompt_path = Path(__file__).parent.parent / "llm_persona" / "system_prompt.md"
        
        # Carregar o prompt base
        if self.prompt_path.exists():
            self.base_prompt = self.prompt_path.read_text(encoding="utf-8")
            logger.info("Persona (system_prompt.md) carregada com sucesso no Orquestrador.")
        else:
            logger.error(f"Arquivo de persona não encontrado em: {self.prompt_path}")
            self.base_prompt = "Você é o JARVIS 2.0. Responda em JSON para gerenciar a planilha."

    def update_memory(self, chat_id: int, role: str, content: str) -> None:
        """Interface para gerenciar e persistir o histórico de conversação do chat"""
        self.memory.add_message(chat_id, role, content)

    async def classify_intent(self, chat_id: int, text: str, save_to_history: bool = True, ignore_history: bool = False, force_json: bool = True, extra_context: list = None) -> dict | str:
        """
        Classifica a intenção do usuário chamando o LLM (Gemini, Groq ou OpenRouter) em formato JSON.
        Substitui dinamicamente as variáveis de prompt (data/hora).
        """
        # Data/hora atual
        datetime_now_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        # Injetar variáveis dinâmicas no prompt
        prompt_with_vars = self.base_prompt.replace("{datetime_now}", datetime_now_str)
        
        # Obter histórico da conversa
        history = self.memory.get_history(chat_id) if not ignore_history else []
        
        # Montar a lista de mensagens no formato clássico
        messages = [{"role": "system", "content": prompt_with_vars}]
        
        # Adicionar o histórico
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
            
        # Injetar contexto extra se fornecido (temporário)
        if extra_context:
            messages.extend(extra_context)
            
        # Se formos salvar no histórico, adicionamos a última mensagem do usuário
        if save_to_history:
            messages.append({"role": "user", "content": text})
            self.update_memory(chat_id, "user", text)
            
        last_error = None
        
        # Priorizar Gemini (se configurado), seguido de Groq e OpenRouter
        for provider in ["Gemini", "Groq", "OpenRouter"]:
            try:
                if provider == "Gemini" and self.gemini_api_key:
                    # Conversão para o formato do Google Gemini API
                    gemini_contents = []
                    system_prompt = messages[0]["content"]
                    
                    # Converte histórico para o formato do Gemini
                    for msg in messages[1:]:
                        role = "user" if msg["role"] == "user" else "model"
                        gemini_contents.append({
                            "role": role,
                            "parts": [{"text": msg["content"]}]
                        })
                    
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_api_key}"
                    headers = {"Content-Type": "application/json"}
                    payload = {
                        "contents": gemini_contents,
                        "systemInstruction": {
                            "parts": [{"text": system_prompt}]
                        },
                        "generationConfig": {
                            "temperature": 0.2
                        }
                    }
                    if force_json:
                        payload["generationConfig"]["responseMimeType"] = "application/json"
                        
                    logger.info("Enviando requisição de intenção ao Google Gemini...")
                    async with httpx.AsyncClient(timeout=45.0) as client:
                        resp = await client.post(url, headers=headers, json=payload)
                        resp.raise_for_status()
                        
                        response_json = resp.json()
                        raw_content = response_json["candidates"][0]["content"]["parts"][0]["text"]
                        
                        if force_json:
                            parsed_json = json.loads(raw_content)
                            logger.info(f"Intenção classificada com Gemini: {parsed_json.get('action')}")
                            return parsed_json
                        else:
                            return raw_content

                elif provider == "Groq" and self.groq_api_key:
                    url = "https://api.groq.com/openai/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {self.groq_api_key}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": "llama-3.3-70b-versatile", 
                        "messages": messages,
                        "temperature": 0.2
                    }
                    if force_json:
                        payload["response_format"] = {"type": "json_object"}
                        
                    logger.info("Enviando requisição de intenção ao Groq...")
                    async with httpx.AsyncClient(timeout=45.0) as client:
                        resp = await client.post(url, headers=headers, json=payload)
                        resp.raise_for_status()
                        
                        response_json = resp.json()
                        raw_content = response_json["choices"][0]["message"]["content"]
                        
                        if force_json:
                            parsed_json = json.loads(raw_content)
                            logger.info(f"Intenção classificada com Groq: {parsed_json.get('action')}")
                            return parsed_json
                        else:
                            return raw_content

                elif provider == "OpenRouter" and self.openrouter_api_key:
                    url = "https://openrouter.ai/api/v1/chat/completions"
                    headers = {
                        "Authorization": f"Bearer {self.openrouter_api_key}",
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": "google/gemini-2.5-flash",
                        "messages": messages,
                        "temperature": 0.2
                    }
                    if force_json:
                        payload["response_format"] = {"type": "json_object"}
                        
                    logger.info("Enviando requisição de intenção ao OpenRouter...")
                    async with httpx.AsyncClient(timeout=45.0) as client:
                        resp = await client.post(url, headers=headers, json=payload)
                        resp.raise_for_status()
                        
                        response_json = resp.json()
                        raw_content = response_json["choices"][0]["message"]["content"]
                        
                        if force_json:
                            parsed_json = json.loads(raw_content)
                            logger.info(f"Intenção classificada com OpenRouter: {parsed_json.get('action')}")
                            return parsed_json
                        else:
                            return raw_content

            except Exception as e:
                logger.warning(f"Falha ao chamar {provider}: {e}")
                last_error = e
                
        # Se todos falharem
        return {"action": "chat", "response": f"Erro interno de processamento da IA: todos os provedores falharam. Detalhe: {last_error}"}

    def validate_action(self, chat_id: int, action: dict) -> tuple[bool, dict]:
        """Sempre retorna válido no novo fluxo simplificado"""
        return True, action

    def feedback_loop(self, action_type: str, err_msg: str) -> dict:
        """Fallback autônomo em caso de falha de execução da ferramenta"""
        logger.error(f"Erro ao executar a ação '{action_type}': {err_msg}")
        return {
            "action": "chat",
            "response": f"⚠️ Ocorreu um erro ao acessar a planilha de clientes:\n\n`{err_msg}`"
        }

    async def _summarize_and_prune(self, chat_id: int) -> None:
        """Poda e resume o histórico de conversação se estiver muito longo"""
        pass

    async def process(self, chat_id: int, user_input: str, on_action_start=None) -> dict:
        """
        Ponto de entrada central do Harness para gerenciamento do Sheets de Clientes.
        """
        # 1. Sanitizar entrada
        cleaned_input = self.security.sanitize_input(user_input)
        
        # 2. Verificar Rate Limiting
        allowed, wait_time = self.security.check_rate_limit(chat_id)
        if not allowed:
            return {
                "action": "chat",
                "response": f"⚠️ Você está enviando mensagens rápido demais. Por favor, aguarde {wait_time} segundos."
            }
            
        # 3. Moderar conteúdo
        if not self.security.moderate_content(cleaned_input):
            return {
                "action": "chat",
                "response": "⚠️ Não posso processar mensagens contendo esse tipo de conteúdo ou instruções perigosas."
            }
        
        # 3.5. Verificar se o histórico precisa de resumo e poda
        await self._summarize_and_prune(chat_id)

        # 4. Classificar Intenção via LLM
        result = await self.classify_intent(chat_id, cleaned_input, save_to_history=True)
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except Exception:
                result = {"action": "chat", "response": result}
                
        # 5. Validar Ação
        is_safe, validated_action = self.validate_action(chat_id, result)
        if not is_safe:
            return validated_action
            
        action_type = validated_action.get("action", "chat")
        
        # Invocar callback de ação se fornecido para feedback visual (UX)
        if on_action_start:
            try:
                await on_action_start(action_type, validated_action)
            except Exception as e:
                logger.warning(f"Erro ao executar callback on_action_start: {e}")
        
        # 6. Execução das Ferramentas
        try:
            if action_type == "sheets_resumo":
                res, err = customer_sheets.get_sheets_summary()
                if err:
                    return self.feedback_loop(action_type, err)
                return {
                    "action": "chat",
                    "response": res
                }
                
            elif action_type == "sheets_buscar":
                query = validated_action.get("query", "")
                if not query:
                    return {"action": "chat", "response": "Quem você gostaria de buscar na tabela de clientes?"}
                res, err = customer_sheets.search_customer_by_name(query)
                if err:
                    return self.feedback_loop(action_type, err)
                return {
                    "action": "chat",
                    "response": res
                }
                
            elif action_type == "sheets_adicionar":
                name = validated_action.get("name", "")
                gender = validated_action.get("gender", "")
                birth_date = validated_action.get("birth_date", "")
                
                if not name:
                    return {"action": "chat", "response": "Por favor, informe o nome do cliente a ser adicionado."}
                if not birth_date:
                    return {"action": "chat", "response": "Por favor, informe a data de nascimento do cliente."}
                    
                res, err = customer_sheets.add_customer_record(name, gender, birth_date)
                if err:
                    return self.feedback_loop(action_type, err)
                return {
                    "action": "chat",
                    "response": res
                }
                
            else:
                # Chat Geral ou outra ação não mapeada
                response_text = validated_action.get("response", "Desculpe, não entendi como processar sua solicitação.")
                return {
                    "action": "chat",
                    "response": response_text
                }
                
        except Exception as e:
            logger.error(f"Erro ao executar ação '{action_type}': {e}")
            return self.feedback_loop(action_type, str(e))
