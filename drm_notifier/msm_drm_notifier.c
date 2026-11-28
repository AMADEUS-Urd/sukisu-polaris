/* MIUI 风格的 drm blank 通知链：供触摸驱动接收亮/息屏事件 */
#include <linux/notifier.h>
#include <linux/export.h>
#include <linux/types.h>
#include <drm/drm_notifier.h>

static BLOCKING_NOTIFIER_HEAD(drm_notifier_list);

int drm_register_client(struct notifier_block *nb)
{
	return blocking_notifier_chain_register(&drm_notifier_list, nb);
}
EXPORT_SYMBOL(drm_register_client);

int drm_unregister_client(struct notifier_block *nb)
{
	return blocking_notifier_chain_unregister(&drm_notifier_list, nb);
}
EXPORT_SYMBOL(drm_unregister_client);

int drm_notifier_call_chain(unsigned long val, void *v)
{
	return blocking_notifier_call_chain(&drm_notifier_list, val, v);
}
EXPORT_SYMBOL(drm_notifier_call_chain);

void report_esd_panel_dead(void) { }
EXPORT_SYMBOL(report_esd_panel_dead);

void set_skip_panel_dead(bool on) { }
EXPORT_SYMBOL(set_skip_panel_dead);

/* MIUI 私有显示辅助 API 的空实现（触摸驱动调用，非必需功能） */
void drm_dsi_ulps_enable(bool en) { }
EXPORT_SYMBOL(drm_dsi_ulps_enable);

void drm_panel_reset_skip_enable(bool en) { }
EXPORT_SYMBOL(drm_panel_reset_skip_enable);
