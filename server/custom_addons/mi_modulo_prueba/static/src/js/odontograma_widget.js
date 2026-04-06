/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class OdontogramaWidget extends Component {
  static template = "odontograma.OdontogramaWidget";
  static props = { ...standardFieldProps };

  setup() {
    this.state = useState({
      tipo: "perm",
      modo: "caries",
      colorSeleccionado: "red",
    });
  }

  _findRecord(dienteId, cara) {
    const list = this.props.record.data[this.props.name];
    if (!list || !list.records) return null;
    return list.records.find(
      (r) =>
        parseInt(r.data.diente_numero) === parseInt(dienteId) &&
        (cara ? r.data.cara === cara : !r.data.cara),
    );
  }

  async onCaraClick(id, cara, ev) {
    if (this.state.modo !== "caries") return;
    const existing = this._findRecord(id, cara);
    const color = this.state.colorSeleccionado;

    if (color === "white") {
      if (existing)
        await this.props.record.update({
          [this.props.name]: [[2, existing.id, false]],
        });
    } else {
      const procMap = {
        red: "caries",
        blue: "limpieza",
        black: "extraccion",
        "#00ff00": "realizado",
      };
      const proc = procMap[color] || "caries";
      if (existing) {
        await existing.update({ procedimiento: proc });
      } else {
        await this.props.record.update({
          [this.props.name]: [
            [
              0,
              0,
              {
                diente_numero: parseInt(id),
                procedimiento: proc,
                cara: cara,
                notas: "",
              },
            ],
          ],
        });
      }
    }
  }

  async onDienteClick(id, ev) {
    if (this.state.modo === "caries") return;
    const modo = this.state.modo;
    const existing = this._findRecord(id, null);

    if (existing && existing.data.procedimiento === modo) {
      await this.props.record.update({
        [this.props.name]: [[2, existing.id, false]],
      });
    } else {
      // Acción Otro y demás ahora crean el registro correctamente
      await this.props.record.update({
        [this.props.name]: [
          [
            0,
            0,
            {
              diente_numero: parseInt(id),
              procedimiento: modo,
              cara: false,
              notas: modo === "otro" ? "Personalizado: " : "",
            },
          ],
        ],
      });
    }
  }

  getDienteColor(id, cara) {
    const list = this.props.record.data[this.props.name];
    if (!list || !list.records) return "white";
    const map = {
      caries: "red",
      limpieza: "blue",
      extraccion: "black",
      realizado: "#00ff00",
    };
    const rec = list.records.find(
      (r) =>
        parseInt(r.data.diente_numero) === parseInt(id) && r.data.cara === cara,
    );
    return rec ? map[rec.data.procedimiento] || "red" : "white";
  }

  hasTratamiento(id, tipo) {
    const list = this.props.record.data[this.props.name];
    if (!list || !list.records) return false;
    return list.records.some(
      (r) =>
        parseInt(r.data.diente_numero) === parseInt(id) &&
        r.data.procedimiento === tipo,
    );
  }

  getDientes(u) {
    const p = [18, 17, 16, 15, 14, 13, 12, 11, 21, 22, 23, 24, 25, 26, 27, 28];
    const pi = [48, 47, 46, 45, 44, 43, 42, 41, 31, 32, 33, 34, 35, 36, 37, 38];
    const t = [55, 54, 53, 52, 51, 61, 62, 63, 64, 65];
    const ti = [85, 84, 83, 82, 81, 71, 72, 73, 74, 75];
    return u === "sup"
      ? this.state.tipo === "perm"
        ? p
        : t
      : this.state.tipo === "perm"
        ? pi
        : ti;
  }
}
registry.category("fields").add("odontograma_widget", {
  component: OdontogramaWidget,
  supportedTypes: ["one2many"],
});
