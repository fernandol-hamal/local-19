/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component, useState, useRef, onWillUnmount } from "@odoo/owl";

export class AudioRecorderField extends Component {
  setup() {
    this.canvasRef = useRef("waveCanvas");
    this.state = useState({
      isRecording: false,
      interimText: "", // Lo que se está procesando ahora mismo
      errorMsg: null,
    });

    this.recognition = null;
    this.audioContext = null;
    this.stream = null;
    this.lastFinalTranscript = ""; // Para no repetir texto anterior

    this.initSpeechRecognition();
    onWillUnmount(() => this.stopAudioResources());
  }

  initSpeechRecognition() {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    this.recognition = new SpeechRecognition();
    this.recognition.continuous = true;
    this.recognition.interimResults = true; // CRÍTICO: permite ver el texto mientras hablas
    this.recognition.lang = "es-ES";

    this.recognition.onresult = (event) => {
      let interimTranscript = "";
      let finalTranscriptChunk = "";

      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscriptChunk += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      // 1. Actualizamos el texto "fantasma" que el usuario ve en gris
      this.state.interimText = interimTranscript || "Escuchando...";

      // 2. Si hay texto finalizado, lo inyectamos al campo de Odoo de inmediato
      if (finalTranscriptChunk) {
        const currentVal = this.props.record.data[this.props.name] || "";
        const separator = currentVal ? " " : "";

        // Actualización automática del campo sin clics
        this.props.record.update({
          [this.props.name]:
            currentVal + separator + finalTranscriptChunk.trim(),
        });
      }
    };
  }

  async toggleRecording() {
    if (this.state.isRecording) {
      this.stopRecording();
    } else {
      this.state.interimText = "Iniciando...";
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({
          audio: true,
        });
        this.recognition.start();
        this.state.isRecording = true;
        setTimeout(() => this.startVisualizer(), 100);
      } catch (e) {
        alert("Error al acceder al micrófono");
      }
    }
  }

  stopRecording() {
    if (this.recognition) this.recognition.stop();
    this.state.isRecording = false;
    this.state.interimText = "";
    this.stopAudioResources();
  }

  stopAudioResources() {
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    if (this.audioContext) this.audioContext.close();
  }

  startVisualizer() {
    if (!this.canvasRef.el) return;
    this.audioContext = new (
      window.AudioContext || window.webkitAudioContext
    )();
    const source = this.audioContext.createMediaStreamSource(this.stream);
    const analyser = this.audioContext.createAnalyser();
    analyser.fftSize = 32;
    source.connect(analyser);
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const ctx = this.canvasRef.el.getContext("2d");

    const draw = () => {
      if (!this.state.isRecording) return;
      requestAnimationFrame(draw);
      analyser.getByteFrequencyData(dataArray);
      ctx.clearRect(0, 0, this.canvasRef.el.width, this.canvasRef.el.height);
      ctx.fillStyle = "#00a884";
      let x = 0;
      for (let i = 0; i < dataArray.length; i++) {
        const h = (dataArray[i] / 255) * this.canvasRef.el.height;
        ctx.fillRect(x, (this.canvasRef.el.height - h) / 2, 3, h);
        x += 5;
      }
    };
    draw();
  }

  clearContent() {
    this.props.record.update({ [this.props.name]: false });
  }
}

AudioRecorderField.template = "mi_modulo_prueba.AudioRecorderField";
AudioRecorderField.props = { ...standardFieldProps };
registry.category("fields").add("audio_recorder", {
  component: AudioRecorderField,
  supportedTypes: ["char", "text"],
});
