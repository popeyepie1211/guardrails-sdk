// test/mock-model.js
import guardrail from '../src/index.js';

// 1. SIMULATE A REAL MODEL
// This represents a typical non-neural network model (like a Loan Approval model)
const AI_Model = {
  predict: async (data) => {
    // Artificial delay to simulate processing time
    await new Promise(resolve => setTimeout(resolve, 100)); 
    
    // Simple logic: Approve if credit score > 700
    return {
      status: data.creditScore > 700 ? "Approved" : "Rejected",
      confidence: 0.98
    };
  }
};

// 2. INITIALIZE THE SDK
// In a real app, these values would come from your Guardrail Dashboard
guardrail.init({
  apiKey: "user_secret_pk_12345",
  modelId: "loan_risk_model_v1",
  endpoint: "http://localhost:3000/v1/ingest" // Points to a local test server
});

// 3. WRAP THE MODEL
// This activates the Proxy hook
const securedModel = guardrail.wrap(AI_Model);

// 4. GENERATE TEST TRAFFIC
console.log("🚀 Starting Mock AI Predictions...");

const runTest = async () => {
  // Generate 5 predictions to see them fill the buffer
  for (let i = 0; i < 5; i++) {
    const score = Math.floor(Math.random() * (850 - 500 + 1)) + 500;
    console.log(`[Test] Requesting prediction for Credit Score: ${score}`);
    
    const result = await securedModel.predict({ creditScore: score });
    console.log(`[Test] Result: ${result.status}`);
  }
  
  console.log("\n⏳ Waiting 5 seconds for the Buffer to flush automatically...");
};

runTest();