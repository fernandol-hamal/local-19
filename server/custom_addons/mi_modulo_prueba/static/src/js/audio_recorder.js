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
    // Si ya está escuchando, lo apagamos
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

      if (apiKey) {
        await this.startDeepgram(apiKey.trim());
      } else {
        alert(
          "Error: No se encontró la API Key en Ajustes > Parámetros del sistema.",
        );
      }
    } catch (error) {
      console.error("Error al obtener API Key:", error);
    }
  }

  async startDeepgram(apiKey) {
    const url = `wss://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&language=es&interim_results=true`;
    this.socket = new WebSocket(url, ["token", apiKey]);

    this.socket.onopen = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        this.mediaRecorder = new MediaRecorder(stream, {
          mimeType: "audio/webm",
        });
        this.mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0 && this.socket?.readyState === 1) {
            this.socket.send(e.data);
          }
        };
        this.mediaRecorder.start(250);
        this.state.isListening = true;
      } catch (err) {
        console.error("No se pudo acceder al micro:", err);
        this.stopAll();
      }
    };

    this.socket.onmessage = (message) => {
      const received = JSON.parse(message.data);
      let transcript = received.channel.alternatives[0].transcript;

      if (
        !transcript ||
        transcript.includes("bytes") ||
        transcript.match(/^\d+\.\d+/)
      )
        return;

      const transcriptLower = transcript.toLowerCase().trim();

      if (!this.state.isRecording && transcriptLower.includes("hola")) {
        this.state.isRecording = true;
        return;
      }

      if (this.state.isRecording) {
        if (received.is_final) {
          this.state.interimText = "";
          this.updateOdooValue(transcript);
          this.extractDataAndFill(transcriptLower);
        } else {
          this.state.interimText = transcript;
        }
      }
    };

    this.socket.onclose = () => this.stopAll();
    this.socket.onerror = () => this.stopAll();
  }

  updateOdooValue(text) {
    const prevValue = this.props.record.data[this.props.name] || "";
    this.props.record.update({
      [this.props.name]: (prevValue + " " + text).trim(),
    });
  }

  extractDataAndFill(text) {
    const dataToUpdate = {};

    // Mapeo de Especialidades (tipServ)
    const especialidadesMap = {
      general: "general",
      ortodoncia: "ortodoncia",
      brackets: "ortodoncia",
      endodoncia: "endodoncia",
      periodoncia: "periodoncia",
      odontopediatría: "odontopediatria",
      niños: "odontopediatria",
      cirugía: "cirugia",
      implantes: "implantologia",
      prótesis: "prostodoncia",
      estética: "estetica",
      diagnóstico: "diagnostico",
    };

    if (text.includes("especialidad")) {
      for (let key in especialidadesMap) {
        if (text.includes(key)) {
          dataToUpdate.tipServ = especialidadesMap[key];
          break;
        }
      }
    }

    // Consultorio
    const consultorioMatch = text.match(
      /consultorio\s*(\d+|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)/,
    );
    if (consultorioMatch) {
      const wordToNum = {
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
      let val = consultorioMatch[1];
      const finalNum = wordToNum[val] || parseInt(val);
      if (!isNaN(finalNum)) dataToUpdate.consultorio = finalNum;
    }

    // Fecha (fechaHistoria)
    if (text.includes("fecha")) {
      const months = {
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
      const match = text.match(/(\d{1,2})\s*de\s*([a-z]+)/);
      if (match && months[match[2]]) {
        const dateStr = `${new Date().getFullYear()}-${months[match[2]]}-${match[1].padStart(2, "0")}`;
        dataToUpdate.fechaHistoria = deserializeDate(dateStr);
      }
    }

    // Motivo
    if (text.includes("motivo")) {
      const parts = text.split("motivo");
      if (parts[1]) dataToUpdate.motivo = parts[1].replace(/^es\s*/, "").trim();
    }

    if (Object.keys(dataToUpdate).length > 0) {
      this.props.record.update(dataToUpdate);
    }
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
