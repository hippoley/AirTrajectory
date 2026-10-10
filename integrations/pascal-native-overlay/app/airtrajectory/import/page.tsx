'use client'

import { useState } from 'react'
import Link from 'next/link'

// Loaded *inside* the pinned upstream Pascal Editor, not an alternative canvas.
export default function ImportPrivateResidence() {
  const [file, setFile] = useState<File | null>(null)
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  async function openScene() {
    if (!file || busy) return
    setBusy(true)
    setStatus('Checking local SceneGraph…')
    try {
      if (file.size > 15_000_000) throw new Error('Scene file exceeds 15 MB')
      const source = await file.text()
      const graph = JSON.parse(source)
      if (!graph || typeof graph !== 'object' || !graph.nodes || !Array.isArray(graph.rootNodeIds)) throw new Error('Expected Pascal native SceneGraph {nodes, rootNodeIds}')
      const nodes = Object.values(graph.nodes) as Array<{type?:string,id?:string}>
      if (!nodes.some(n => n.type === 'zone')) throw new Error('No native rooms (zone) found')
      if (nodes.some(n => !n.id || typeof n.type !== 'string')) throw new Error('Invalid native node')
      setStatus('Saving into local Pascal Scene store…')
      const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(source))
      const checksum = Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2,'0')).join('')
      const id = 'private-residence-' + checksum.slice(0,16)
      const saved = await fetch('/api/scenes/' + encodeURIComponent(id), {cache:'no-store'})
      if (saved.status === 404) {
        const response = await fetch('/api/scenes', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,name:file.name.replace(/\.json$/i,'').slice(0,180)||'Private residence',projectId:'airtrajectory-local',graph})})
        if (!response.ok) throw new Error('Native save failed (' + response.status + '): ' + (await response.text()).slice(0,260))
      } else if (saved.ok) {
        const existing = await saved.json()
        if (JSON.stringify(existing.graph?.nodes) !== JSON.stringify(graph.nodes)) throw new Error('Scene ID exists but content differs; import blocked')
      } else {
        throw new Error('Native scene lookup failed (' + saved.status + ')')
      }
      setStatus('Opening complete Pascal Editor…')
      window.location.assign('/scene/' + encodeURIComponent(id))
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Scene import failed')
      setBusy(false)
    }
  }
  return <main style={{minHeight:'100vh',background:'#131822',color:'#f4f7fc',fontFamily:'system-ui',padding:'min(6vw,70px)'}}>
    <div style={{maxWidth:780,margin:'0 auto'}}>
      <p style={{letterSpacing:'.12em',color:'#7bd5ae',fontSize:12,fontWeight:700}}>AIRTRAJECTORY × PASCAL NATIVE</p>
      <h1 style={{fontSize:'clamp(30px,5vw,48px)',fontWeight:750,margin:'12px 0'}}>Open your private residence</h1>
      <p style={{color:'#aebaca',lineHeight:1.7}}>Load a native SceneGraph into the genuine Pascal 2D/3D Editor with its Build, Paint and Items tools. Your file goes only to this Pascal server; it is not uploaded to GitHub.</p>
      <div style={{border:'1px solid #3d4a60',background:'#1d2634',padding:28,borderRadius:16,marginTop:28}}>
        <label htmlFor="native-scene-file" style={{display:'block',fontWeight:600,marginBottom:12}}>Native Pascal SceneGraph JSON</label>
        <input id="native-scene-file" type="file" accept=".json,application/json" onChange={e=>{setFile(e.target.files?.[0]??null);setStatus('')}} style={{width:'100%',marginBottom:22}}/>
        <button type="button" disabled={!file||busy} onClick={openScene} style={{cursor:file&&!busy?'pointer':'not-allowed',border:0,borderRadius:9,padding:'12px 20px',fontWeight:750,background:'#a6edcc',color:'#10221c',opacity:file&&!busy?1:.5}}>{busy?'Importing…':'Import and open complete Editor'}</button>
        <p role="status" aria-live="polite" style={{color:'#e0e9f2',marginTop:14,fontSize:13}}>{status}</p>
      </div>
      <p style={{color:'#aebaca',marginTop:24,fontSize:13}}>CAD walls and opening positions are subject to architectural review; loading a scene does not approve its engineering or CONTAM metadata.</p>
      <Link href="/scenes" style={{color:'#9cdec2'}}>Browse saved native Pascal scenes →</Link>
    </div>
  </main>
}
