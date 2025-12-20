import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchChannels, fetchChannelById, ChannelSummary, ChannelDetail } from '../services/channels'

export default function ChannelViewSimple() {
  const { channelSlug } = useParams<{ channelSlug?: string }>()
  const [channels, setChannels] = useState<ChannelSummary[] | null>(null)
  const [loadingChannels, setLoadingChannels] = useState(true)
  const [channel, setChannel] = useState<ChannelSummary | null>(null)
  const [channelDetail, setChannelDetail] = useState<ChannelDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Load channel list (cached by service)
  useEffect(() => {
    let cancelled = false
    setLoadingChannels(true)
    fetchChannels()
      .then((list) => {
        if (cancelled) return
        setChannels(list)
        setLoadingChannels(false)
      })
      .catch((err) => {
        if (cancelled) return
        console.error('Failed to load channels list', err)
        setLoadingChannels(false)
      })
    return () => { cancelled = true }
  }, [])

  // Resolve slug (or numeric id) -> channel
  useEffect(() => {
    if (!channels || !channelSlug) {
      setChannel(null)
      return
    }

    // Try numeric id first
    const asNum = Number(channelSlug)
    const found = channels.find((c) => c.id === asNum || c.name === channelSlug || c.display_name === channelSlug)
    setChannel(found ?? null)
  }, [channels, channelSlug])

  // Fetch channel metadata when we have an id
  useEffect(() => {
    if (!channel) {
      setChannelDetail(null)
      return
    }
    let cancelled = false
    setLoadingDetail(true)
    fetchChannelById(channel.id)
      .then((detail) => {
        if (cancelled) return
        setChannelDetail(detail)
        setLoadingDetail(false)
      })
      .catch((err) => {
        if (cancelled) return
        console.error('Failed to load channel detail', err)
        setLoadingDetail(false)
      })
    return () => { cancelled = true }
  }, [channel?.id])

  if (loadingChannels) {
    return <div style={{ padding: 16 }}>Loading channels…</div>
  }

  if (!channelSlug) {
    return (
      <div style={{ padding: 16 }}>
        <h2>No channel selected</h2>
      </div>
    )
  }

  if (!channel) {
    return (
      <div style={{ padding: 16 }}>
        <h2>Channel not found</h2>
      </div>
    )
  }

  if (loadingDetail) {
    return (
      <div style={{ padding: 16 }}>
        <h2># {channel.display_name || channel.name}</h2>
        <p style={{ opacity: 0.6 }}>Loading channel details…</p>
      </div>
    )
  }

  if (!channelDetail) {
    return (
      <div style={{ padding: 16 }}>
        <h2># {channel.display_name || channel.name}</h2>
        <p style={{ opacity: 0.6 }}>Channel details not available</p>
      </div>
    )
  }

  return (
    <div style={{ padding: 16 }}>
      <header>
        <h2># {channelDetail.display_name || channelDetail.name}</h2>
        {channelDetail.description && (
          <p style={{ marginTop: 8, opacity: 0.8 }}>{channelDetail.description}</p>
        )}
        {channelDetail.created_at && (
          <small style={{ display: 'block', marginTop: 8, opacity: 0.6 }}>
            Created {new Date(channelDetail.created_at).toLocaleDateString()}
          </small>
        )}
      </header>
    </div>
  )
}
