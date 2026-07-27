import type { DeviceNode } from '../types/topology'

interface DeviceInfoPanelProps {
  device: DeviceNode | null
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-4 border-b border-slate-200 py-2 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-mono text-slate-900">{value}</span>
    </div>
  )
}

export function DeviceInfoPanel({ device }: DeviceInfoPanelProps) {
  if (!device) {
    return (
      <div className="flex h-full items-center justify-center p-6 text-center text-slate-400">
        Tap a device to see its details
      </div>
    )
  }

  return (
    <div className="p-6">
      <h2 className="mb-4 text-lg font-semibold text-slate-900">{device.label}</h2>
      <Row label="Status" value={device.online ? 'Online' : 'Offline'} />
      <Row label="IP Address" value={device.ip_address ?? '—'} />
      <Row label="MAC Address" value={device.mac_address ?? '—'} />
      <Row label="Vendor" value={device.vendor ?? '—'} />
    </div>
  )
}
