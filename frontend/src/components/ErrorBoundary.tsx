import React from 'react'

interface State {
  hasError: boolean
}

export default class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  constructor(props: any) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: any) {
    console.error('ErrorBoundary caught:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 text-red-400 bg-[#2b2d31]">
          <h3 className="font-bold">Something went wrong.</h3>
          <p className="text-sm">Please reload the page or contact a developer.</p>
        </div>
      )
    }

    return this.props.children
  }
}
