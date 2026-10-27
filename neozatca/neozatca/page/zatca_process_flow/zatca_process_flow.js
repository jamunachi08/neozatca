function nz_ready(fn) {
	if (window.neozatca && typeof neozatca[fn] === "function") return true;
	frappe.msgprint({
		title: __("Reload needed"),
		message: __("NeoZatca was just updated. Reload this page (Ctrl+Shift+R, or Cmd+Shift+R on Mac) to load the new version."),
		indicator: "orange",
	});
	return false;
}

// Copyright (c) 2026, Neotec Integrated Solutions and contributors
// ZATCA Process Flow — the whole journey as a transit line; every station opens the document that finishes it.

frappe.pages["zatca-process-flow"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("ZATCA Process Flow"), single_column: true });
	wrapper.nzpf = new ZatcaProcessFlow(page);
};

frappe.pages["zatca-process-flow"].on_page_show = function (wrapper) {
	const pf = wrapper.nzpf;
	if (!pf || !pf.loaded) return;
	const wanted = frappe.route_options && frappe.route_options.company;
	frappe.route_options = null;
	if (wanted && wanted !== pf.company_field.get_value()) {
		pf.company_field.set_value(wanted); // triggers refresh
	} else {
		// Coming back from a document: re-read the site so the station you just fixed turns green.
		pf.refresh();
	}
};

const NZPF_STATUS = {
	done: { label: __("Done"), icon: "✓" },
	progress: { label: __("Running"), icon: "…" },
	todo: { label: __("To do"), icon: "" },
	warn: { label: __("Needs attention"), icon: "!" },
	error: { label: __("Failed"), icon: "×" },
};

class ZatcaProcessFlow {
	constructor(page) {
		this.page = page;
		this.selected = null;
		this.inject_style();
		this.company_field = page.add_field({
			fieldtype: "Link", fieldname: "company", label: __("Company"), options: "Company",
			default: (frappe.route_options && frappe.route_options.company) || frappe.defaults.get_user_default("Company"),
			change: () => { this.selected = null; this.refresh(); },
		});
		page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
		page.add_inner_button(__("Control Center"), () => frappe.set_route("zatca-control-center"));
		frappe.route_options = null;
		this.$root = $(`<div class="nzpf"></div>`).appendTo(page.main);
		frappe.realtime.on("neozatca_onboarding", (d) => d && d.complete && this.refresh());
		this.refresh();
	}

	refresh() {
		return frappe.call("neozatca.zatca.process_flow.get_flow", { company: this.company_field.get_value() || null })
			.then(({ message }) => {
				const first = !this.loaded;
				this.loaded = true;
				this.data = message;
				if (message.company && this.company_field.get_value() !== message.company) {
					this.company_field.set_value(message.company);
				}
				if (!this.selected || !message.steps.find((s) => s.key === this.selected)) {
					this.selected = message.next || (message.steps[0] && message.steps[0].key);
				}
				this.render(first);
			});
	}

	stage(key) { return this.data.stages.find((s) => s.key === key); }

	render(first) {
		const d = this.data;
		if (!d.steps.length) {
			this.$root.html(`<div class="nzpf-empty">${__("Create a Company first. NeoZatca walks you from there.")}</div>`);
			return;
		}
		const pct = d.progress.total ? Math.round((100 * d.progress.done) / d.progress.total) : 0;
		const next = d.steps.find((s) => s.key === d.next);
		const finished = d.progress.done === d.progress.total;

		// Progress bar split into the five stage colours, each filled by its own share of done steps.
		const segments = d.stages.map((st) => {
			const req = d.steps.filter((s) => s.stage === st.key && s.required);
			const done = req.filter((s) => s.status === "done").length;
			if (!req.length) return "";
			return `<div class="nzpf-seg" style="flex:${req.length}" title="${frappe.utils.escape_html(__(st.label))}">
				<span style="width:${(100 * done) / req.length}%;background:${st.color}"></span></div>`;
		}).join("");

		this.$root.html(`
			<header class="nzpf-head">
				<div class="nzpf-head-text">
					<h3>${finished ? __("{0} is live on ZATCA", [frappe.utils.escape_html(d.company)]) : __("Get {0} live on ZATCA", [frappe.utils.escape_html(d.company)])}</h3>
					<p>${__("{0} of {1} required steps done", [d.progress.done, d.progress.total])}, ${__(d.phase)}.
					   ${__("Each station shows what's missing and opens the document that fixes it.")}</p>
				</div>
				${next ? `<button class="btn btn-primary nzpf-continue nzpf-primary" style="--c:${this.stage(next.stage).color}">${__("Continue with: {0}", [frappe.utils.escape_html(next.title)])}</button>` : ""}
			</header>
			<div class="nzpf-bar" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100">${segments}</div>
			<div class="nzpf-body">
				<nav class="nzpf-line" aria-label="${__("Process steps")}">${this.line_html()}</nav>
				<section class="nzpf-panel" aria-live="polite"></section>
			</div>`);

		this.$root.find(".nzpf-continue").on("click", () => this.select(d.next, true));
		this.$root.find(".nzpf-station").on("click", (e) => this.select($(e.currentTarget).data("key")));
		this.render_panel();
		if (first && d.next) {
			this.$root.find(`.nzpf-station[data-key="${d.next}"] .nzpf-dot`).addClass("nzpf-pulse");
		}
	}

	line_html() {
		const d = this.data;
		let n = 0;
		return d.stages.map((st) => {
			const steps = d.steps.filter((s) => s.stage === st.key);
			const stations = steps.map((s) => {
				n += 1;
				const status = NZPF_STATUS[s.status] || NZPF_STATUS.todo;
				return `
				<button class="nzpf-station is-${s.status} ${s.key === this.selected ? "is-selected" : ""} ${s.key === d.next ? "is-next" : ""}"
					data-key="${s.key}" style="--c:${st.color}" aria-current="${s.key === this.selected ? "step" : "false"}">
					<span class="nzpf-track ${s.status === "done" ? "is-solid" : ""}"></span>
					<span class="nzpf-dot" aria-hidden="true">${status.icon || n}</span>
					<span class="nzpf-station-text">
						<span class="nzpf-station-title">${frappe.utils.escape_html(s.title)}${s.required ? "" : ` <em>${__("optional")}</em>`}</span>
						<span class="nzpf-station-status">${status.label}</span>
					</span>
				</button>`;
			}).join("");
			return `
			<div class="nzpf-stage" style="--c:${st.color}">
				<div class="nzpf-stage-name"><span>${frappe.utils.escape_html(__(st.label))}</span><span dir="rtl" lang="ar">${frappe.utils.escape_html(st.label_ar)}</span></div>
				${stations}
			</div>`;
		}).join("");
	}

	select(key, scroll) {
		this.selected = key;
		this.$root.find(".nzpf-station").removeClass("is-selected").attr("aria-current", "false");
		this.$root.find(`.nzpf-station[data-key="${key}"]`).addClass("is-selected").attr("aria-current", "step");
		this.render_panel();
		if (scroll && window.innerWidth < 900) {
			this.$root.find(".nzpf-panel")[0].scrollIntoView({ behavior: "smooth", block: "center" });
		}
	}

	render_panel() {
		const d = this.data;
		const idx = d.steps.findIndex((s) => s.key === this.selected);
		const s = d.steps[idx];
		if (!s) return;
		const st = this.stage(s.stage);
		const status = NZPF_STATUS[s.status] || NZPF_STATUS.todo;
		const esc = frappe.utils.escape_html;
		const actions = s.actions.slice().sort((a, b) => (b.primary ? 1 : 0) - (a.primary ? 1 : 0));
		const prev = d.steps[idx - 1], next = d.steps[idx + 1];

		const $p = this.$root.find(".nzpf-panel");
		// Narrow screens: open the panel right under the tapped station instead of below the whole line.
		if (window.innerWidth < 900) {
			$p.addClass("is-inline").insertAfter(this.$root.find(`.nzpf-station[data-key="${s.key}"]`));
		} else if ($p.hasClass("is-inline")) {
			$p.removeClass("is-inline").appendTo(this.$root.find(".nzpf-body"));
		}
		$p.attr("style", `--c:${st.color}`).html(`
			<div class="nzpf-panel-stage">${__("Step {0} of {1}", [idx + 1, d.steps.length])}, ${esc(__(st.label))}</div>
			<div class="nzpf-titles"><h4>${esc(s.title)}</h4><span class="nzpf-panel-ar" dir="rtl" lang="ar">${esc(s.title_ar)}</span></div>
			<div class="nzpf-state is-${s.status}"><span>${status.label}</span>${s.required ? "" : `<span class="nzpf-opt">${__("optional")}</span>`}</div>
			<p class="nzpf-detail">${esc(s.detail || "")}</p>
			${s.help ? `<p class="nzpf-help">${esc(s.help)}</p>` : ""}
			<div class="nzpf-actions">
				${actions.map((a, i) => `<button class="btn btn-sm ${a.primary ? "btn-primary nzpf-primary" : "btn-default"}" data-i="${i}">${esc(a.label)}</button>`).join("")}
			</div>
			<div class="nzpf-walk">
				${prev ? `<button class="btn btn-xs btn-link nzpf-prev">${__("Previous: {0}", [esc(prev.title)])}</button>` : "<span></span>"}
				${next ? `<button class="btn btn-xs btn-link nzpf-next">${__("Next: {0}", [esc(next.title)])}</button>` : ""}
			</div>`);
		$p.find(".nzpf-actions button").on("click", (e) => this.run(actions[$(e.currentTarget).data("i")]));
		$p.find(".nzpf-prev").on("click", () => this.select(prev.key));
		$p.find(".nzpf-next").on("click", () => this.select(next.key));
	}

	run(a) {
		if (a.type === "route") {
			if (a.route[0] === "url") return window.open(a.route[1], "_blank", "noopener");
			if (a.options && Object.keys(a.options).length) frappe.route_options = a.options;
			return frappe.set_route(...a.route);
		}
		if (a.type === "new_doc") {
			const values = Object.assign({}, a.values);
			const children = {};
			Object.keys(values).forEach((k) => { if (Array.isArray(values[k])) { children[k] = values[k]; delete values[k]; } });
			return frappe.new_doc(a.doctype, values, (doc) => {
				Object.entries(children).forEach(([field, rows]) =>
					rows.forEach((r) => Object.assign(frappe.model.add_child(doc, field), r)));
			});
		}
		if (a.type === "method") {
			const go = () => frappe.call({ method: a.method, args: a.args, freeze: true, freeze_message: __("Working…") })
				.then(() => { frappe.show_alert({ message: __("Done"), indicator: "green" }); this.refresh(); });
			return a.confirm ? frappe.confirm(a.confirm, go) : go();
		}
		if (a.type === "js") return this[`js_${a.handler}`](a.args || {});
	}

	js_quick_setup({ company, environment }) {
		nz_ready("quick_setup") && neozatca.quick_setup(company, { environment });
	}

	js_fetch_address({ address }) {
		nz_ready("national_address_dialog") && frappe.db.get_doc("Address", address).then((doc) => neozatca.national_address_dialog({
			defaults: doc,
			on_pick: (a) => frappe.call({ method: "neozatca.zatca.national_address.apply_to_address", args: { address, result: a }, freeze: true })
				.then(() => { frappe.show_alert({ message: __("Company address updated"), indicator: "green" }); this.refresh(); }),
		}));
	}

	js_fix_items({ company }) {
		frappe.call("neozatca.zatca.process_flow.get_items_without_tax").then(({ message: items }) => {
			const esc = frappe.utils.escape_html;
			const d = new frappe.ui.Dialog({
				title: __("Give items a VAT template"),
				size: "large",
				fields: [
					{ fieldtype: "Link", fieldname: "template", label: __("Item Tax Template"), options: "Item Tax Template", reqd: 1,
						get_query: () => ({ filters: { company, disabled: 0 } }),
						description: __("Usually “KSA VAT 15% Selling”. Use 0% / Exempt templates only for items that qualify.") },
					{ fieldtype: "HTML", fieldname: "list", options: `
						<div class="nzpf-pick">
							<label><input type="checkbox" class="nzpf-all" checked> ${__("Select all ({0} shown)", [items.length])}</label>
							${items.map((it) => `<label><input type="checkbox" class="nzpf-it" value="${esc(it.name)}" checked>
								<a href="/app/item/${encodeURIComponent(it.name)}" target="_blank">${esc(it.item_name || it.name)}</a>
								<span class="text-muted">${esc(it.item_group || "")}</span></label>`).join("")}
						</div>` },
				],
				primary_action_label: __("Apply template"),
				primary_action: (v) => {
					const picked = d.$wrapper.find(".nzpf-it:checked").map((_, el) => el.value).get();
					if (!picked.length) return frappe.msgprint(__("Select at least one item."));
					frappe.call({ method: "neozatca.zatca.process_flow.apply_item_tax_template", args: { template: v.template, items: picked },
						freeze: true, freeze_message: __("Updating items…") })
						.then(({ message }) => {
							d.hide();
							frappe.show_alert({ message: __("{0} item(s) updated", [message.updated]), indicator: "green" });
							if (message.failed.length) frappe.msgprint(message.failed.map((f) => `${esc(f.item)}: ${esc(f.error)}`).join("<br>"), __("Some items were not updated"));
							this.refresh();
						});
				},
			});
			d.show();
			d.$wrapper.find(".nzpf-all").on("change", (e) => d.$wrapper.find(".nzpf-it").prop("checked", e.target.checked));
		});
	}

	js_review_customers() {
		frappe.call("neozatca.zatca.process_flow.get_customers_needing_attention").then(({ message: rows }) => {
			const esc = frappe.utils.escape_html;
			new frappe.ui.Dialog({
				title: __("Customers to review"),
				size: "large",
				fields: [{ fieldtype: "HTML", options: `
					<p class="text-muted small">${__("Standard (B2B) invoices need the customer's 15-digit VAT number and address. Open each customer to fix it.")}</p>
					<table class="table table-sm small"><thead><tr><th>${__("Customer")}</th><th>${__("VAT")}</th><th>${__("Problem")}</th></tr></thead><tbody>
					${rows.map((r) => `<tr><td><a href="/app/customer/${encodeURIComponent(r.name)}" target="_blank">${esc(r.customer_name || r.name)}</a></td>
						<td>${esc(r.tax_id || "")}</td><td>${esc(r.problems)}</td></tr>`).join("")}
					</tbody></table>` }],
			}).show();
		});
	}

	inject_style() {
		if (document.getElementById("nzpf-style")) return;
		$(`<style id="nzpf-style">
			.nzpf { max-width: 1120px; margin: 0 auto; padding: 8px 0 40px; }
			.nzpf-empty { padding: 40px 0; color: var(--text-muted); }
			.nzpf-head { display:flex; justify-content:space-between; align-items:flex-end; gap:16px; flex-wrap:wrap; margin: 6px 0 14px; }
			.nzpf-head h3 { margin:0 0 4px; font-size: 1.45rem; font-weight: 650; letter-spacing: -0.01em; }
			.nzpf-head p { margin:0; color: var(--text-muted); max-width: 64ch; }
			.nzpf-bar { display:flex; gap:4px; height:8px; margin-bottom: 22px; }
			.nzpf-seg { background: var(--subtle-fg, var(--gray-100)); border-radius: 4px; overflow:hidden; }
			.nzpf-seg span { display:block; height:100%; transition: width .4s ease; }
			.nzpf-body { display:grid; grid-template-columns: minmax(280px, 380px) 1fr; gap: 28px; align-items:start; }
			@media (max-width: 900px) { .nzpf-body { grid-template-columns: 1fr; } }

			/* The line */
			.nzpf-stage { position: relative; padding-left: 4px; }
			.nzpf-stage-name { display:flex; justify-content:space-between; gap:8px; font-size: var(--text-sm); font-weight:600;
				color: var(--c); padding: 10px 0 6px 52px; }
			.nzpf-stage-name span[dir=rtl] { font-weight: 500; opacity:.85; }
			.nzpf-station { position:relative; display:flex; align-items:center; gap:14px; width:100%; text-align:left;
				background:none; border:0; padding: 9px 10px 9px 0; border-radius: 10px; color: var(--text-color); cursor:pointer; }
			.nzpf-station:hover { background: var(--fg-hover-color); }
			.nzpf-station:focus-visible { outline: 2px solid var(--c); outline-offset: 2px; }
			.nzpf-station.is-selected { background: color-mix(in srgb, var(--c) 12%, transparent); }
			.nzpf-track { position:absolute; left: 21px; top: -12px; bottom: -12px; width: 6px; border-radius: 3px;
				background: repeating-linear-gradient(to bottom, color-mix(in srgb, var(--c) 55%, transparent) 0 8px, transparent 8px 14px); }
			.nzpf-track.is-solid { background: var(--c); }
			.nzpf-stage:first-child .nzpf-station:first-of-type .nzpf-track { top: 50%; }
			.nzpf-stage:last-child .nzpf-station:last-of-type .nzpf-track { bottom: 50%; }
			.nzpf-dot { position:relative; z-index:1; flex:none; width: 30px; height: 30px; margin-left: 9px; border-radius: 50%;
				display:grid; place-items:center; font-size: 13px; font-weight: 700;
				background: var(--card-bg, var(--bg-color)); border: 3px solid var(--c); color: var(--c); }
			.is-done .nzpf-dot { background: var(--c); color: #fff; }
			.is-warn .nzpf-dot { border-color: #D97706; color: #D97706; }
			.is-error .nzpf-dot { border-color: #DC2626; color: #DC2626; }
			.is-progress .nzpf-dot { border-style: dotted; }
			.nzpf-station.is-selected .nzpf-dot { box-shadow: 0 0 0 5px color-mix(in srgb, var(--c) 28%, transparent); }
			.nzpf-pulse { animation: nzpf-pulse 1.4s ease-out 2; }
			@keyframes nzpf-pulse { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--c) 55%, transparent); } 100% { box-shadow: 0 0 0 14px transparent; } }
			@media (prefers-reduced-motion: reduce) { .nzpf-pulse { animation: none; } .nzpf-seg span { transition: none; } }
			.nzpf-station-text { display:flex; flex-direction:column; min-width:0; }
			.nzpf-station-title { font-weight: 600; line-height: 1.25; }
			.nzpf-station-title em { font-style: normal; font-weight: 500; color: var(--text-muted); font-size: var(--text-xs); }
			.nzpf-station-status { font-size: var(--text-xs); color: var(--text-muted); }
			.is-next .nzpf-station-status { color: var(--c); font-weight: 600; }

			/* The panel */
			.nzpf-panel { position: sticky; top: 72px; border-radius: 14px; padding: 22px 24px 18px;
				background: var(--card-bg, var(--bg-color)); border: 1px solid var(--border-color);
				border-top: 6px solid var(--c); }
			.nzpf-panel-stage { font-size: var(--text-sm); color: var(--c); font-weight: 600; }
			.nzpf-titles { display:flex; justify-content:space-between; align-items:baseline; gap:12px; flex-wrap:wrap; margin: 6px 0 12px; }
			.nzpf-panel h4 { margin: 0; font-size: 1.3rem; font-weight: 650; }
			.nzpf-panel-ar { color: var(--text-muted); font-size: 1.05rem; }
			.nzpf-panel.is-inline { position: relative; top: 0; margin: 4px 0 10px 52px; padding: 16px 16px 12px; }
			.nzpf-panel.is-inline::before { content: ""; position: absolute; left: -35px; top: -14px; bottom: -18px; width: 6px; border-radius: 3px;
				background: repeating-linear-gradient(to bottom, color-mix(in srgb, var(--c) 55%, transparent) 0 8px, transparent 8px 14px); }
			.nzpf-panel.is-inline .nzpf-panel-stage { display:none; }
			.nzpf-state { display:flex; gap:8px; align-items:center; margin-bottom: 10px; }
			.nzpf-state span:first-child { font-size: var(--text-sm); font-weight: 600; padding: 2px 10px; border-radius: 999px;
				background: color-mix(in srgb, var(--c) 14%, transparent); color: var(--c); }
			.nzpf-state.is-done span:first-child { background: color-mix(in srgb, #16A34A 15%, transparent); color: #16A34A; }
			.nzpf-state.is-warn span:first-child { background: color-mix(in srgb, #D97706 15%, transparent); color: #B45309; }
			.nzpf-state.is-error span:first-child { background: color-mix(in srgb, #DC2626 15%, transparent); color: #DC2626; }
			.nzpf-opt { font-size: var(--text-xs); color: var(--text-muted); }
			.nzpf-detail { font-size: 1rem; line-height: 1.5; max-width: 62ch; margin: 0 0 6px; }
			.nzpf-help { color: var(--text-muted); font-size: var(--text-sm); max-width: 62ch; }
			.nzpf-actions { display:flex; flex-wrap:wrap; gap:8px; margin: 14px 0 6px; }
			.nzpf-primary { background: var(--c) !important; border-color: var(--c) !important; color: #fff !important; }
			.nzpf-walk { display:flex; justify-content:space-between; gap:8px; border-top: 1px solid var(--border-color); margin-top: 14px; padding-top: 8px; }
			.nzpf-walk .btn-link { color: var(--text-muted); padding-left:0; padding-right:0; }
			.nzpf-pick { max-height: 340px; overflow:auto; display:grid; gap:4px; }
			.nzpf-pick label { display:flex; gap:8px; align-items:center; margin:0; font-weight: 400; }
			.nzpf-pick label:first-child { font-weight: 600; border-bottom: 1px solid var(--border-color); padding-bottom: 6px; margin-bottom: 4px; }
		</style>`).appendTo("head");
	}
}
