import { useState, useEffect, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { apiClient } from '../api/client'

/**
 * Parse Grok source list output into individual posts grouped by topic.
 *
 * Grok returns topics as ### or #### headers, each containing numbered
 * posts with Author, Post, Link, Engagement fields. We extract every
 * individual post so the user can run pipeline on each one separately.
 *
 * Returns: { topics: [{ title, posts: [{ author, content, body }] }] }
 */
function parseSources(text) {
  if (!text) return []

  // Split into topic sections — match ### or #### followed by number or "Topic"
  const topicPattern = /\n(?=#{3,4}\s+(?:Topic\s+)?\d)/
  const hasTopics = /#{3,4}\s+(?:Topic\s+)?\d/.test(text)
  if (!hasTopics) return []

  const sections = text.split(topicPattern)
  const topics = []

  for (const section of sections) {
    const trimmed = section.trim()
    if (!trimmed) continue

    // Extract topic title from ### or #### header
    const headerMatch = trimmed.match(/^#{3,4}\s+(?:Topic\s+)?(\d+)[.:]\s*(.+?)\s*\n([\s\S]*)$/)
    if (!headerMatch) continue

    const topicTitle = headerMatch[2].replace(/^\*+|\*+$/g, '').trim()
    const topicBody = headerMatch[3]

    // Extract individual posts within this topic
    // Format A: "1. **Author**: Name (@handle)...\n**Post**: ...\n**Link**: ...\n**Engagement**: ..."
    // Format B: "- **Post 1**: Author (@handle)...\n\"content\"...\n[Link](...)"
    const posts = []

    // Split on numbered posts: "N. **Author**:" or "- **Post N**:"
    const postParts = topicBody.split(/\n(?=\d+\.\s+\*\*Author\*\*:|(?:- )?\*\*Post\s+\d+\*\*:)/)

    for (const part of postParts) {
      const postTrimmed = part.trim()
      if (!postTrimmed) continue

      // Try Format A: "1. **Author**: Name (@handle)..."
      const fmtA = postTrimmed.match(/^\d+\.\s+\*\*Author\*\*:\s*(.+?)(?:\n|$)([\s\S]*)$/)
      if (fmtA) {
        const author = fmtA[1].trim()
        const rest = fmtA[2]
        // Extract post content
        const postMatch = rest.match(/\*\*Post\*\*:\s*["""]?([\s\S]*?)["""]?\s*(?:\*\*Link\*\*:|$)/)
        const postContent = postMatch ? postMatch[1].trim() : ''
        posts.push({ author, content: postContent, body: postTrimmed })
        continue
      }

      // Try Format B: "- **Post 1**: Author (@handle)..."
      const fmtB = postTrimmed.match(/^(?:- )?\*\*Post\s+\d+\*\*:\s*(.+?)(?:\n|$)([\s\S]*)$/)
      if (fmtB) {
        const author = fmtB[1].trim()
        const rest = fmtB[2]
        // Content is usually in quotes on next lines
        const contentMatch = rest.match(/["""](.+?)["""]/s)
        const postContent = contentMatch ? contentMatch[1].trim() : rest.split('\n')[0].trim()
        posts.push({ author, content: postContent, body: postTrimmed })
        continue
      }
    }

    // If we couldn't parse individual posts, treat entire topic as one item
    if (posts.length === 0) {
      posts.push({ author: '', content: '', body: topicBody.trim() })
    }

    topics.push({ title: `${headerMatch[1]}. ${topicTitle}`, posts })
  }

  return topics
}

function SourceListRunPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const promptId = searchParams.get('prompt_id')

  const [prompt, setPrompt] = useState(null)
  const [output, setOutput] = useState(null)
  const [storyId, setStoryId] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [statusMsg, setStatusMsg] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (promptId) {
      apiClient(`/prompts/${promptId}`)
        .then(setPrompt)
        .catch((err) => setError(err.message))
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [promptId])

  async function handleRun() {
    setLoading(true)
    setError(null)
    setStatusMsg('Sending request...')
    try {
      const data = await apiClient('/pipeline/source-list', {
        method: 'POST',
        body: JSON.stringify({ prompt_id: parseInt(promptId, 10) }),
      })

      if (!data || !data.story_id) {
        throw new Error('Server did not return a story_id')
      }

      setStoryId(data.story_id)
      setStatusMsg('Waiting for Grok API response (this may take up to 60 seconds)...')

      // Start polling
      pollRef.current = setInterval(async () => {
        try {
          const status = await apiClient(`/pipeline/status/${data.story_id}`)
          if (status.status === 'completed') {
            clearInterval(pollRef.current)
            setOutput(status.source_list_output)
            setStatusMsg(null)
            setLoading(false)
          } else if (status.status === 'failed') {
            clearInterval(pollRef.current)
            const failedRun = status.runs.find(r => r.status === 'failed')
            setError(failedRun ? failedRun.error_message : 'Pipeline failed')
            setStatusMsg(null)
            setLoading(false)
          }
        } catch (err) {
          clearInterval(pollRef.current)
          setError(err.message)
          setStatusMsg(null)
          setLoading(false)
        }
      }, 2000)
    } catch (err) {
      setError(err.message)
      setStatusMsg(null)
      setLoading(false)
    }
  }

  function handleRunPipeline(topicBody) {
    navigate(`/pipeline?story_id=${storyId}&selected=${encodeURIComponent(topicBody.substring(0, 2000))}`)
  }

  if (!promptId) {
    return <p>No prompt_id provided. Go to <a href="/prompts">Prompt Library</a> and run a Source List.</p>
  }

  const topics = parseSources(output)

  return (
    <div>
      <h1>Source List Runner</h1>

      {prompt && (
        <div style={{ background: '#f4f4f4', padding: '1rem', borderRadius: '6px', marginBottom: '1rem' }}>
          <h3>{prompt.name}</h3>
          {prompt.opportunity && <p><strong>Opportunity:</strong> {prompt.opportunity} | <strong>State:</strong> {prompt.state}</p>}
          {prompt.publications && <p><strong>Publications:</strong> {prompt.publications}</p>}
          {prompt.pitches_per_week && <p><strong>Pitches/Week:</strong> {prompt.pitches_per_week}</p>}
          <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: '#fff', borderRadius: '4px', border: '1px solid #ddd' }}>
            <strong>Prompt Text:</strong>
            <p style={{ whiteSpace: 'pre-wrap', margin: '0.5rem 0 0', fontSize: '0.9rem', color: '#333' }}>{prompt.prompt_text}</p>
          </div>
        </div>
      )}

      {!output && (
        <div>
          <button onClick={handleRun} disabled={loading} style={{ padding: '0.75rem 2rem', fontSize: '1rem' }}>
            {loading ? 'Running...' : 'Run Source List'}
          </button>
          {statusMsg && <p style={{ color: '#007bff', marginTop: '0.5rem' }}>{statusMsg}</p>}
        </div>
      )}

      {error && <p style={{ color: 'red', marginTop: '1rem' }}>Error: {error}</p>}

      {output && (
        <div style={{ marginTop: '1rem' }}>
          <h2>Results</h2>
          <p style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
            Each source below can be sent to the pipeline individually.
          </p>

          {topics.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {topics.map((topic, ti) => (
                <div key={ti}>
                  <h3 style={{ borderBottom: '2px solid #007bff', paddingBottom: '0.5rem', marginBottom: '0.75rem' }}>
                    {topic.title}
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', paddingLeft: '0.5rem' }}>
                    {topic.posts.map((post, pi) => (
                      <div
                        key={pi}
                        style={{
                          padding: '1rem',
                          borderRadius: '6px',
                          border: '1px solid #ddd',
                          background: '#f9f9f9',
                        }}
                      >
                        {post.author && (
                          <div style={{ fontWeight: 'bold', fontSize: '0.95rem', marginBottom: '0.5rem' }}>
                            {post.author}
                          </div>
                        )}
                        {post.content && (
                          <div style={{ fontSize: '0.9rem', color: '#333', marginBottom: '0.5rem', fontStyle: 'italic' }}>
                            "{post.content}"
                          </div>
                        )}
                        <pre style={{ whiteSpace: 'pre-wrap', margin: '0.5rem 0', fontSize: '0.8rem', color: '#555' }}>
                          {post.body}
                        </pre>
                        <button
                          onClick={() => handleRunPipeline(post.body)}
                          style={{
                            padding: '0.4rem 1.25rem',
                            fontSize: '0.9rem',
                            background: '#007bff',
                            color: '#fff',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                          }}
                        >
                          Run Pipeline
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <pre style={{ background: '#f9f9f9', padding: '1rem', borderRadius: '6px', whiteSpace: 'pre-wrap', border: '1px solid #ddd' }}>
              {output}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

export default SourceListRunPage
