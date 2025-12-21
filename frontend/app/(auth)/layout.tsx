export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-100">
      <div className="w-full max-w-md bg-white border rounded-lg shadow-sm p-8">
        {children}
      </div>
    </div>
  )
}
