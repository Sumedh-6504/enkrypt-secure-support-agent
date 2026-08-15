import { useState, useRef, useEffect, useCallback } from 'react'
import { LayoutDashboard, MessageSquare, ChartBar as BarChart3, Settings2, CircleUser as UserCircle, Bot, Send, Sparkles, ChevronRight, LogOut, Plus, Clock, CircleCheck as CheckCircle2, Cpu, FileSearch, GitMerge, Zap, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Skeleton } from '@/components/ui/skeleton'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { Separator } from '@/components/ui/separator'
import { Badge } from '@/components/ui/badge'

/* ─── Types ────────────────────────────────────────────────────────────────── */

interface Citation {
  id: string
  label: string
  snippet: string
  source: string
  page?: number
}

interface ReasoningStep {
  step: number
  icon: React.ReactNode
  title: string
  content: string
  duration: string
}

interface Message {
  id: string
  role: 'user' | 'agent'
  content: string
  citations?: Citation[]
  reasoning?: ReasoningStep[]
  timestamp: Date
}

/* ─── Sample Data ──────────────────────────────────────────────────────────── */

const SAMPLE_MESSAGES: Message[] = [
  {
    id: '1',
    role: 'user',
    content: 'What are our Q4 compliance requirements for the new AI data processing pipeline?',
    timestamp: new Date(Date.now() - 8 * 60 * 1000),
  },
  {
    id: '2',
    role: 'agent',
    content:
      'Based on your enterprise compliance framework [Doc 1] and the current SEC data governance policy [Doc 2], your Q4 AI pipeline must meet three critical requirements:\n\n1. **Data Lineage Tracking** — Full audit trails for all training data ingestion points must be logged and retained for 7 years per [Doc 1].\n\n2. **Bias Assessment Protocol** — A certified third-party algorithmic audit is required prior to production deployment, as outlined in the AI Ethics Charter [Doc 3].\n\n3. **Cross-border Transfer Compliance** — Any EU-origin data must be processed within EU-designated compute regions under the updated DPA addendum [Doc 2].',
    citations: [
      {
        id: 'doc1',
        label: 'Doc 1',
        snippet:
          'Section 4.2: All AI/ML data pipelines must maintain comprehensive lineage records for a minimum retention period of seven (7) years from the date of last model update.',
        source: 'Enterprise Compliance Framework v3.1',
        page: 42,
      },
      {
        id: 'doc2',
        label: 'Doc 2',
        snippet:
          'Article 46(2)(c): Standard contractual clauses adopted by a supervisory authority must be applied for any transfer of personal data to third countries, effective Q3 2024.',
        source: 'SEC Data Governance Policy 2024',
        page: 11,
      },
      {
        id: 'doc3',
        label: 'Doc 3',
        snippet:
          'Principle 7: All production AI systems must undergo independent algorithmic bias assessment by a certified external auditor at least once per fiscal quarter.',
        source: 'Nexus AI Ethics Charter',
        page: 28,
      },
    ],
    reasoning: [
      {
        step: 1,
        icon: <FileSearch className="size-3.5" />,
        title: 'Query Decomposition',
        content: 'Parsed the query into three semantic axes: compliance scope (AI pipeline), temporal context (Q4), and document corpus (enterprise policies).',
        duration: '0.18s',
      },
      {
        step: 2,
        icon: <Cpu className="size-3.5" />,
        title: 'Vector Retrieval',
        content: 'Searched 2,847 document chunks across 14 policy repositories. Retrieved top 8 results with cosine similarity > 0.87.',
        duration: '0.31s',
      },
      {
        step: 3,
        icon: <GitMerge className="size-3.5" />,
        title: 'Cross-Reference Validation',
        content: 'Identified 3 primary regulatory intersections between SEC guidelines and internal frameworks. Flagged 1 potential conflict in cross-border data clauses (resolved).',
        duration: '0.44s',
      },
      {
        step: 4,
        icon: <Zap className="size-3.5" />,
        title: 'Response Synthesis',
        content: 'Structured findings into actionable compliance items, prioritized by implementation urgency and regulatory risk score (high → medium).',
        duration: '0.22s',
      },
    ],
    timestamp: new Date(Date.now() - 7 * 60 * 1000),
  },
  {
    id: '3',
    role: 'user',
    content: 'Which internal teams need to sign off on the bias assessment before go-live?',
    timestamp: new Date(Date.now() - 4 * 60 * 1000),
  },
  {
    id: '4',
    role: 'agent',
    content:
      'Per the AI Deployment Runbook [Doc 4], the following stakeholders must provide formal sign-off before any AI system goes live:\n\n- **Legal & Privacy** — Reviews data processing agreements and ensures GDPR/CCPA alignment [Doc 4].\n- **Chief Risk Officer** — Validates the external audit report against internal risk thresholds.\n- **Product Security** — Confirms penetration testing and model inversion attack mitigations [Doc 5].\n- **Business Unit Owner** — Provides final deployment authorization in the governance portal.',
    citations: [
      {
        id: 'doc4',
        label: 'Doc 4',
        snippet:
          'Stage 4 — Production Gate: Written approval from Legal & Privacy, CRO, and Product Security is a hard requirement. No deployment may proceed without all three sign-offs logged in the GovernancePortal.',
        source: 'AI Deployment Runbook v2.4',
        page: 19,
      },
      {
        id: 'doc5',
        label: 'Doc 5',
        snippet:
          'Requirement PS-07: Model inversion and membership inference attacks must be assessed and mitigated prior to production exposure of any model trained on PII-adjacent datasets.',
        source: 'Product Security Standards 2024',
        page: 34,
      },
    ],
    reasoning: [
      {
        step: 1,
        icon: <FileSearch className="size-3.5" />,
        title: 'Stakeholder Mapping',
        content: 'Identified the question relates to governance sign-off workflows. Scoped retrieval to runbooks, RACI matrices, and deployment checklists.',
        duration: '0.14s',
      },
      {
        step: 2,
        icon: <Cpu className="size-3.5" />,
        title: 'Document Retrieval',
        content: 'Retrieved 5 relevant documents from the AI governance corpus. Prioritized the Deployment Runbook (v2.4) as the authoritative source.',
        duration: '0.27s',
      },
      {
        step: 3,
        icon: <Zap className="size-3.5" />,
        title: 'Response Synthesis',
        content: 'Mapped approval roles to their primary responsibilities. Added source citations for each stakeholder requirement for auditability.',
        duration: '0.19s',
      },
    ],
    timestamp: new Date(Date.now() - 3 * 60 * 1000),
  },
]

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'chatbot', label: 'AI Chatbot', icon: MessageSquare, active: true },
  { id: 'analytics', label: 'Analytics', icon: BarChart3 },
  { id: 'settings', label: 'Settings', icon: Settings2 },
  { id: 'profile', label: 'Profile', icon: UserCircle },
]

/* ─── Sub-components ────────────────────────────────────────────────────────── */

function CitationTag({ citation }: { citation: Citation }) {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span className="inline-flex items-center gap-1 mx-0.5 px-1.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 text-[11px] font-semibold border border-indigo-200/80 cursor-help hover:bg-indigo-100 hover:border-indigo-300 transition-colors align-baseline">
            {citation.label}
          </span>
        </TooltipTrigger>
        <TooltipContent
          side="top"
          align="center"
          className="max-w-[300px] p-0 bg-white border border-slate-200 shadow-xl rounded-xl overflow-hidden"
        >
          <div className="p-3 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-indigo-600">
                {citation.source}
              </span>
              {citation.page && (
                <span className="text-[10px] text-slate-400 font-medium">p. {citation.page}</span>
              )}
            </div>
            <Separator />
            <p className="text-xs text-slate-600 leading-relaxed italic">"{citation.snippet}"</p>
            <div className="flex items-center gap-1 text-[10px] text-slate-400">
              <ExternalLink className="size-2.5" /> View full document
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

function renderContent(content: string, citations?: Citation[]) {
  if (!citations?.length) {
    return <span className="whitespace-pre-line">{content}</span>
  }

  const parts = content.split(/(\[Doc \d+\])/g)
  return (
    <span className="whitespace-pre-line">
      {parts.map((part, i) => {
        const match = part.match(/\[Doc (\d+)\]/)
        if (match) {
          const citation = citations.find((c) => c.label === `Doc ${match[1]}`)
          if (citation) return <CitationTag key={i} citation={citation} />
        }
        return renderMarkdown(part, i)
      })}
    </span>
  )
}

function renderMarkdown(text: string, key: number) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  if (parts.length === 1) return <span key={key}>{text}</span>
  return (
    <span key={key}>
      {parts.map((p, i) => {
        if (p.startsWith('**') && p.endsWith('**')) {
          return <strong key={i} className="font-semibold">{p.slice(2, -2)}</strong>
        }
        return p
      })}
    </span>
  )
}

function ReasoningPanel({ steps }: { steps: ReasoningStep[] }) {
  return (
    <div className="relative bg-gradient-to-br from-white/95 to-indigo-50/70 backdrop-blur-sm border border-indigo-100/80 rounded-xl p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <div className="flex items-center justify-center size-5 rounded-full bg-indigo-600">
          <Sparkles className="size-3 text-white" />
        </div>
        <span className="text-xs font-semibold text-indigo-700 tracking-wide uppercase">
          Chain-of-Thought Reasoning
        </span>
        <Badge variant="secondary" className="ml-auto text-[10px] px-2 py-0 h-4 bg-indigo-50 text-indigo-600 border-indigo-200">
          {steps.reduce((acc, s) => acc + parseFloat(s.duration), 0).toFixed(2)}s total
        </Badge>
      </div>

      <div className="relative pl-5">
        <div className="absolute left-2 top-0 bottom-0 w-px bg-gradient-to-b from-indigo-300 via-indigo-200 to-transparent" />

        <div className="space-y-4">
          {steps.map((step, idx) => (
            <div key={step.step} className="relative">
              <div className="absolute -left-[21px] top-0.5 flex items-center justify-center size-4 rounded-full bg-white border-2 border-indigo-300 shadow-sm">
                <div className="text-indigo-600">{step.icon}</div>
              </div>
              <div className={cn(idx < steps.length - 1 && 'pb-1')}>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-semibold text-slate-700">{step.title}</span>
                  <span className="flex items-center gap-1 text-[10px] text-slate-400">
                    <Clock className="size-2.5" />
                    {step.duration}
                  </span>
                  <CheckCircle2 className="size-3 text-emerald-500 ml-auto" />
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">{step.content}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function UserMessage({ message }: { message: Message }) {
  return (
    <div className="flex justify-end items-end gap-2.5 mb-6">
      <div className="max-w-[68%]">
        <div className="bg-indigo-600 text-white rounded-2xl rounded-br-md px-4 py-3 text-sm leading-relaxed shadow-sm shadow-indigo-200">
          {message.content}
        </div>
        <p className="text-right text-[10px] text-slate-400 mt-1 pr-1">
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
      <Avatar className="size-8 shrink-0 ring-2 ring-white shadow-sm">
        <AvatarFallback className="bg-slate-700 text-white text-xs font-bold">JD</AvatarFallback>
      </Avatar>
    </div>
  )
}

function AgentMessage({ message }: { message: Message }) {
  return (
    <div className="flex items-start gap-2.5 mb-6">
      <div className="size-8 rounded-full bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center shrink-0 shadow-sm shadow-indigo-200">
        <Bot className="size-4 text-white" />
      </div>
      <div className="max-w-[78%] min-w-0">
        <div className="bg-slate-100 text-slate-800 rounded-2xl rounded-tl-md px-4 py-3 text-sm leading-relaxed">
          {renderContent(message.content, message.citations)}
        </div>

        {message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mt-2 pl-1">
            <span className="text-[10px] text-slate-400 font-medium">Sources:</span>
            {message.citations.map((c) => (
              <CitationTag key={c.id} citation={c} />
            ))}
          </div>
        )}

        {message.reasoning && message.reasoning.length > 0 && (
          <Accordion type="single" collapsible className="mt-2">
            <AccordionItem value="reasoning" className="border-0">
              <AccordionTrigger className="py-1.5 px-3 text-xs text-indigo-600 font-semibold hover:text-indigo-800 hover:no-underline gap-1.5 w-fit rounded-lg hover:bg-indigo-50 transition-colors data-[state=open]:bg-indigo-50 data-[state=open]:text-indigo-800">
                <Sparkles className="size-3 text-indigo-500" />
                View Intelligence
              </AccordionTrigger>
              <AccordionContent className="pb-0 pt-2">
                <ReasoningPanel steps={message.reasoning} />
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        )}

        <p className="text-[10px] text-slate-400 mt-1.5 pl-1">
          {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </p>
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-start gap-2.5 mb-6">
      <div className="size-8 rounded-full bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center shrink-0 shadow-sm shadow-indigo-200">
        <Bot className="size-4 text-white" />
      </div>
      <div className="bg-slate-100 rounded-2xl rounded-tl-md px-4 py-3.5">
        <div className="flex gap-1.5 items-center">
          <span className="size-2 rounded-full bg-slate-400 animate-bounce [animation-delay:0ms]" />
          <span className="size-2 rounded-full bg-slate-400 animate-bounce [animation-delay:150ms]" />
          <span className="size-2 rounded-full bg-slate-400 animate-bounce [animation-delay:300ms]" />
        </div>
      </div>
    </div>
  )
}

function MessageSkeleton() {
  return (
    <div className="p-6 space-y-8">
      <div className="flex justify-end items-end gap-2.5">
        <div className="space-y-1">
          <Skeleton className="h-11 w-52 rounded-2xl rounded-br-md" />
        </div>
        <Skeleton className="size-8 rounded-full shrink-0" />
      </div>

      <div className="flex items-start gap-2.5">
        <Skeleton className="size-8 rounded-full shrink-0" />
        <div className="space-y-2">
          <Skeleton className="h-24 w-80 rounded-2xl rounded-tl-md" />
          <Skeleton className="h-3.5 w-36 rounded-full" />
          <Skeleton className="h-7 w-28 rounded-lg" />
        </div>
      </div>

      <div className="flex justify-end items-end gap-2.5">
        <Skeleton className="h-10 w-44 rounded-2xl rounded-br-md" />
        <Skeleton className="size-8 rounded-full shrink-0" />
      </div>

      <div className="flex items-start gap-2.5">
        <Skeleton className="size-8 rounded-full shrink-0" />
        <div className="space-y-2">
          <Skeleton className="h-32 w-96 max-w-full rounded-2xl rounded-tl-md" />
          <Skeleton className="h-3.5 w-44 rounded-full" />
          <Skeleton className="h-7 w-28 rounded-lg" />
        </div>
      </div>
    </div>
  )
}

/* ─── Main Page ─────────────────────────────────────────────────────────────── */

export default function ChatbotPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isTyping, setIsTyping] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const timer = setTimeout(() => {
      setMessages(SAMPLE_MESSAGES)
      setIsLoading(false)
    }, 2000)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isTyping])

  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || isTyping) return

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    setInputValue('')
    setIsTyping(true)

    try {
      const response = await import('@/lib/api').then(m => m.askQuestion(userMessage.content));
      
      const agentMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: response.answer,
        citations: response.citations,
        reasoning: response.reasoning,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, agentMessage])
    } catch (error) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'agent',
        content: 'I encountered an error connecting to the Nexus intelligence engine. Please ensure the backend server is running.',
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
      console.error('API Error:', error)
    } finally {
      setIsTyping(false)
    }
  }, [inputValue, isTyping])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div
      className="flex h-screen bg-white overflow-hidden"
      style={{ fontFamily: "'Inter', ui-sans-serif, system-ui, sans-serif" }}
    >
      {/* ── Sidebar ──────────────────────────────────────────────────────────── */}
      <aside className="flex flex-col w-64 shrink-0 h-full bg-[oklch(0.988_0.006_286)] border-r border-[oklch(0.9_0.012_286)]">
        {/* Logo */}
        <div className="px-4 pt-5 pb-4">
          <div className="flex items-center gap-2.5 px-2">
            <div className="size-8 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center shadow-sm shadow-indigo-200">
              <Sparkles className="size-4 text-white" />
            </div>
            <div>
              <h1
                className="text-[15px] font-bold text-slate-900 leading-none"
                style={{ fontFamily: "'Plus Jakarta Sans', ui-sans-serif" }}
              >
                Nexus
              </h1>
              <p className="text-[10px] text-indigo-600 font-semibold tracking-wider uppercase leading-none mt-0.5">
                Enterprise AI
              </p>
            </div>
          </div>
        </div>

        {/* New Chat Button */}
        <div className="px-3 mb-3">
          <Button
            className="w-full h-9 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium shadow-sm shadow-indigo-200 gap-1.5 transition-all"
          >
            <Plus className="size-4" />
            New Conversation
          </Button>
        </div>

        <Separator className="mx-3 w-auto bg-[oklch(0.9_0.012_286)]" />

        {/* Nav */}
        <nav className="flex-1 px-2 py-2 space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all text-left group',
                item.active
                  ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-200'
                  : 'text-slate-600 hover:bg-[oklch(0.948_0.016_286)] hover:text-indigo-700'
              )}
            >
              <item.icon
                className={cn(
                  'size-4 shrink-0 transition-colors',
                  item.active ? 'text-white' : 'text-slate-400 group-hover:text-indigo-600'
                )}
              />
              {item.label}
              {item.active && (
                <div className="ml-auto size-1.5 rounded-full bg-white/80" />
              )}
            </button>
          ))}
        </nav>

        <Separator className="mx-3 w-auto bg-[oklch(0.9_0.012_286)]" />

        {/* User Profile */}
        <div className="p-3">
          <div className="flex items-center gap-2.5 px-2 py-2 rounded-lg hover:bg-[oklch(0.948_0.016_286)] transition-colors cursor-pointer group">
            <Avatar className="size-8 shrink-0">
              <AvatarFallback className="bg-slate-700 text-white text-xs font-bold">JD</AvatarFallback>
            </Avatar>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-slate-800 truncate">Jane Doe</p>
              <p className="text-[10px] text-slate-400 truncate">Enterprise Admin</p>
            </div>
            <LogOut className="size-3.5 text-slate-300 group-hover:text-slate-500 transition-colors shrink-0" />
          </div>
        </div>
      </aside>

      {/* ── Main Chat Area ───────────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {/* Chat Header */}
        <header className="flex items-center justify-between px-6 py-3.5 border-b border-slate-100 bg-white/95 backdrop-blur-sm">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center shadow-sm shadow-indigo-200">
              <Bot className="size-5 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2
                  className="text-[15px] font-bold text-slate-900"
                  style={{ fontFamily: "'Plus Jakarta Sans', ui-sans-serif" }}
                >
                  Nexus AI Assistant
                </h2>
                <Badge className="h-4 px-1.5 text-[9px] font-bold bg-indigo-50 text-indigo-700 border-indigo-200 rounded-full">
                  ENTERPRISE
                </Badge>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <p className="text-[11px] text-slate-400">Connected to 2,847 documents</p>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Badge variant="outline" className="text-[11px] text-slate-500 border-slate-200 gap-1 hidden sm:flex">
              <Cpu className="size-3" /> GPT-4o Enterprise
            </Badge>
            <Button variant="ghost" size="icon" className="size-8 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg">
              <Settings2 className="size-4" />
            </Button>
          </div>
        </header>

        {/* Messages */}
        <ScrollArea className="flex-1 min-h-0">
          {isLoading ? (
            <MessageSkeleton />
          ) : (
            <div className="px-6 pt-6 pb-2">
              {messages.map((msg) =>
                msg.role === 'user' ? (
                  <UserMessage key={msg.id} message={msg} />
                ) : (
                  <AgentMessage key={msg.id} message={msg} />
                )
              )}
              {isTyping && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </div>
          )}
        </ScrollArea>

        {/* Input Area */}
        <div className="px-6 pb-6 pt-3 bg-white border-t border-slate-100">
          <div className="relative">
            <div
              className={cn(
                'flex items-end gap-3 rounded-2xl border bg-white px-4 py-3 transition-all shadow-sm',
                'border-slate-200 hover:border-slate-300',
                'focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 focus-within:shadow-md focus-within:shadow-indigo-100'
              )}
            >
              <textarea
                ref={inputRef}
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask anything about your enterprise documents…"
                rows={1}
                className="flex-1 resize-none bg-transparent text-sm text-slate-800 placeholder:text-slate-400 outline-none leading-relaxed max-h-36 overflow-y-auto"
                style={{
                  fontFamily: "'Inter', ui-sans-serif, system-ui, sans-serif",
                }}
              />
              <Button
                onClick={handleSend}
                disabled={!inputValue.trim() || isTyping || isLoading}
                className="size-8 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-200 disabled:text-slate-400 text-white shadow-none shrink-0 transition-all p-0"
              >
                <Send className="size-3.5" />
              </Button>
            </div>
            <p className="text-center text-[10px] text-slate-300 mt-2">
              Press <kbd className="px-1 py-0.5 rounded bg-slate-100 text-slate-500 font-mono text-[10px]">Enter</kbd> to send · <kbd className="px-1 py-0.5 rounded bg-slate-100 text-slate-500 font-mono text-[10px]">Shift+Enter</kbd> for new line
            </p>
          </div>

          {/* Suggested prompts — shown when empty */}
          {messages.length === 0 && !isLoading && (
            <div className="mt-4 grid grid-cols-2 gap-2">
              {[
                'Summarize our Q4 compliance requirements',
                'Which policies need renewal this quarter?',
                'List all AI governance stakeholders',
                'What are our data retention obligations?',
              ].map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => setInputValue(prompt)}
                  className="text-left px-3 py-2.5 rounded-xl border border-slate-200 text-xs text-slate-600 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 transition-all"
                >
                  <ChevronRight className="size-3 inline mr-1 text-slate-300" />
                  {prompt}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
