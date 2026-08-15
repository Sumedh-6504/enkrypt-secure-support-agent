import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Citation {
  id: string;
  label: string;
  snippet: string;
  source: string;
  page?: number;
}

export interface ReasoningStep {
  step: number;
  title: string;
  content: string;
  duration: string;
}

export interface AskResponse {
  question: string;
  answer: string;
  citations: Citation[];
  reasoning: ReasoningStep[];
  security_status: string;
}

export const askQuestion = async (question: string, sessionId: string = 'default_session'): Promise<AskResponse> => {
  const response = await api.post<AskResponse>('/ask', {
    question,
    session_id: sessionId,
  });
  return response.data;
};

export default api;
