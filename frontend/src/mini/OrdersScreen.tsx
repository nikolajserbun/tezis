import { PageHeader } from '../components/ui'
import { useMini } from './context'
import { OrdersList } from './parts'

export function OrdersScreen() {
  const { bumpOrders, haptic, refreshMe } = useMini()

  const refresh = (): void => {
    haptic()
    bumpOrders()
    refreshMe()
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Заказы"
        subtitle="Все покупки, их статус и состав."
        action={
          <button type="button" className="btn-ghost btn-sm" onClick={refresh}>
            Обновить
          </button>
        }
      />
      <OrdersList />
    </div>
  )
}
