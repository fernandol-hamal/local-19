/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, onWillUnmount } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";
import { deserializeDate } from "@web/core/l10n/dates";

export class AudioRecorderField extends Component {
  setup() {
    this.state = useState({
      isListening: false,
      isRecording: false,
      interimText: "",
    });
    this.socket = null;
    this.mediaRecorder = null;
    onWillUnmount(() => this.stopAll());
  }

  async toggleMicrophone() {
    if (this.state.isListening) {
      this.stopAll();
      return;
    }
    try {
      const apiKey = await rpc("/web/dataset/call_kw", {
        model: "ir.config_parameter",
        method: "get_param",
        args: ["denty.deepgram.api_key"],
        kwargs: {},
      });
      if (apiKey) await this.startDeepgram(apiKey.trim());
    } catch (e) {
      console.error("Error API:", e);
    }
  }

  async startDeepgram(apiKey) {
    const url = `wss://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=es&interim_results=true`;
    this.socket = new WebSocket(url, ["token", apiKey]);

    this.socket.onopen = async () => {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm",
      });
      this.mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0 && this.socket?.readyState === 1)
          this.socket.send(e.data);
      };
      this.mediaRecorder.start(250);
      this.state.isListening = true;
    };

    this.socket.onmessage = (message) => {
      const received = JSON.parse(message.data);
      let transcript = received.channel.alternatives[0].transcript;

      // FILTRO DE RUIDO TÉCNICO (Borra el error de "bytes")
      if (
        !transcript ||
        transcript.toLowerCase().includes("bytes") ||
        transcript.match(/^\d+\.\d+/)
      )
        return;

      const text = transcript.toLowerCase().trim();

      // COMANDOS DE CONTROL
      if (!this.state.isRecording && text.includes("hola")) {
        this.state.isRecording = true;
        return;
      }
      if (this.state.isRecording && text.includes("pausa")) {
        this.state.isRecording = false;
        this.state.interimText = "⏸️ PAUSADO";
        return;
      }
      if (text.includes("terminar")) {
        this.stopAll();
        return;
      }

      if (this.state.isRecording) {
        if (received.is_final) {
          this.state.interimText = "";
          this.updateOdooValue(transcript);
          this.extractDataAndFill(text);
        } else {
          this.state.interimText = transcript;
        }
      }
    };

    this.socket.onclose = () => this.stopAll();
  }

  updateOdooValue(text) {
    const fieldName = this.props.name;
    const prevValue = this.props.record.data[fieldName] || "";
    // Aseguramos que sea String puro para evitar el error de binascii Incorrect Padding
    const newValue = (prevValue + " " + text).replace(/\s+/g, " ").trim();
    this.props.record.update({ [fieldName]: String(newValue) });
  }

  extractDataAndFill(text) {
    const data = {};
    const espMap = {
      general: "general",
      ortodoncia: "ortodoncia",
      endodoncia: "endodoncia",
      periodoncia: "periodoncia",
      niños: "odontopediatria",
      cirugía: "cirugia",
      implantes: "implantologia",
      prótesis: "prostodoncia",
      estética: "estetica",
      diagnóstico: "diagnostico",
    };
    if (text.includes("especialidad")) {
      for (let key in espMap) {
        if (text.includes(key)) {
          data.tipServ = espMap[key];
          break;
        }
      }
    }
    const conMatch = text.match(
      /consultorio\s*(\d+|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)/,
    );
    if (conMatch) {
      const w2n = {
        uno: 1,
        dos: 2,
        tres: 3,
        cuatro: 4,
        cinco: 5,
        seis: 6,
        siete: 7,
        ocho: 8,
        nueve: 9,
        diez: 10,
      };
      data.consultorio = w2n[conMatch[1]] || parseInt(conMatch[1]);
    }
    if (text.includes("fecha")) {
      const meses = {
        enero: "01",
        febrero: "02",
        marzo: "03",
        abril: "04",
        mayo: "05",
        junio: "06",
        julio: "07",
        agosto: "08",
        septiembre: "09",
        octubre: "10",
        noviembre: "11",
        diciembre: "12",
      };
      const fMatch = text.match(/(\d{1,2})\s*de\s*([a-z]+)/);
      if (fMatch && meses[fMatch[2]]) {
        data.fechaHistoria = deserializeDate(
          `${new Date().getFullYear()}-${meses[fMatch[2]]}-${fMatch[1].padStart(2, "0")}`,
        );
      }
    }
    if (text.includes("motivo")) {
      const p = text.split("motivo");
      if (p[1]) data.motivo = p[1].replace(/^es\s*/, "").trim();
    }
    if (Object.keys(data).length > 0) this.props.record.update(data);
  }

  stopAll() {
    if (this.mediaRecorder?.state !== "inactive") {
      this.mediaRecorder?.stop();
      this.mediaRecorder?.stream.getTracks().forEach((t) => t.stop());
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
    this.state.isListening = false;
    this.state.isRecording = false;
    this.state.interimText = "";
  }
}

AudioRecorderField.template = "mi_modulo_prueba.AudioRecorderField";
AudioRecorderField.props = { ...standardFieldProps };
registry
  .category("fields")
  .add("audio_recorder", { component: AudioRecorderField });
