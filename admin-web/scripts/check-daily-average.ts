import * as admin from 'firebase-admin';
import * as dotenv from 'dotenv';
import * as path from 'path';

// 환경변수 로드
dotenv.config({ path: path.join(__dirname, '../.env.local') });

// Firebase Admin 초기화
if (!admin.apps.length) {
  const projectId = process.env.FIRESTORE_PROJECT_ID;
  const credentialsJson = process.env.GOOGLE_APPLICATION_CREDENTIALS_JSON_BASE64;

  if (!projectId) {
    console.error('FIRESTORE_PROJECT_ID 환경변수가 설정되지 않았습니다.');
    process.exit(1);
  }

  try {
    if (credentialsJson) {
      const decoded = Buffer.from(credentialsJson, 'base64').toString('utf-8');
      const serviceAccount = JSON.parse(decoded);
      admin.initializeApp({
        credential: admin.credential.cert(serviceAccount),
        projectId,
      });
    } else if (process.env.GOOGLE_APPLICATION_CREDENTIALS) {
      admin.initializeApp({
        credential: admin.credential.cert(process.env.GOOGLE_APPLICATION_CREDENTIALS),
        projectId,
      });
    } else {
      // 기본 인증 사용 (GCP 환경에서 실행 시)
      admin.initializeApp({
        projectId,
      });
    }
  } catch (error) {
    console.error('Firebase Admin initialization failed:', error);
    process.exit(1);
  }
}

const db = admin.firestore();

async function checkDailyAverage() {
  try {
    // KST(UTC+9) 기준으로 날짜 계산
    const now = new Date();
    const kstOffset = 9 * 60 * 60 * 1000;
    const kstNow = new Date(now.getTime() + kstOffset);
    
    // 최근 30일 데이터 조회
    const daysToAnalyze = 30;
    const kstDaysAgoStart = new Date(kstNow.getFullYear(), kstNow.getMonth(), kstNow.getDate() - daysToAnalyze);
    const daysAgoStart = new Date(kstDaysAgoStart.getTime() - kstOffset);
    
    console.log(`\n📊 최근 ${daysToAnalyze}일간 통계 분석 중...`);
    console.log(`기간: ${kstDaysAgoStart.toISOString().split('T')[0]} ~ ${kstNow.toISOString().split('T')[0]} (KST)\n`);
    
    const recentEventsSnapshot = await db.collection("email_events")
      .where("timestamp", ">=", daysAgoStart)
      .get();
    
    console.log(`총 이벤트 수: ${recentEventsSnapshot.size}건\n`);
    
    // 일별 집계
    const dailyStatsMap = new Map<string, { total: number; aiDetected: number }>();
    
    recentEventsSnapshot.docs.forEach(doc => {
      const data = doc.data();
      
      // 날짜 추출 (KST 기준)
      let dateStr: string;
      if (data.created_at && data.created_at.toDate) {
        const eventDate = new Date(data.created_at.toDate().getTime() + kstOffset);
        dateStr = eventDate.toISOString().split('T')[0];
      } else if (data.timestamp && data.timestamp.toDate) {
        const eventDate = new Date(data.timestamp.toDate().getTime() + kstOffset);
        dateStr = eventDate.toISOString().split('T')[0];
      } else {
        return; // 날짜 정보 없으면 스킵
      }
      
      // 일별 통계 초기화
      if (!dailyStatsMap.has(dateStr)) {
        dailyStatsMap.set(dateStr, { total: 0, aiDetected: 0 });
      }
      
      const dailyStats = dailyStatsMap.get(dateStr)!;
      dailyStats.total++;
      
      // AI 검출 여부 확인 (LLM 토큰이 있으면 AI 검출로 간주)
      const hasAiDetection = (data.llm_input_tokens || 0) > 0 || (data.llm_output_tokens || 0) > 0;
      if (hasAiDetection) {
        dailyStats.aiDetected++;
      }
    });
    
    // 평균 계산
    const dailyStatsArray = Array.from(dailyStatsMap.entries())
      .map(([date, stats]) => ({ date, ...stats }))
      .sort((a, b) => a.date.localeCompare(b.date));
    
    const avgDailyProcessed = dailyStatsArray.length > 0 
      ? Math.round(dailyStatsArray.reduce((sum, stats) => sum + stats.total, 0) / dailyStatsArray.length)
      : 0;
    const avgDailyAiDetected = dailyStatsArray.length > 0
      ? Math.round(dailyStatsArray.reduce((sum, stats) => sum + stats.aiDetected, 0) / dailyStatsArray.length)
      : 0;
    
    // 결과 출력
    console.log('='.repeat(60));
    console.log('📈 하루 평균 통계');
    console.log('='.repeat(60));
    console.log(`\n✅ 하루 평균 메일 확인 수: ${avgDailyProcessed.toLocaleString()}통`);
    console.log(`🤖 하루 평균 AI 검출 수: ${avgDailyAiDetected.toLocaleString()}통`);
    console.log(`\n📅 집계 기간: ${dailyStatsArray.length}일`);
    console.log(`📊 총 처리 메일: ${recentEventsSnapshot.size.toLocaleString()}통`);
    console.log(`🤖 총 AI 검출: ${dailyStatsArray.reduce((sum, stats) => sum + stats.aiDetected, 0).toLocaleString()}통`);
    
    if (dailyStatsArray.length > 0) {
      console.log(`\n📊 일별 상세 통계 (최근 10일):`);
      console.log('-'.repeat(60));
      dailyStatsArray.slice(-10).forEach(stat => {
        const percentage = stat.total > 0 ? ((stat.aiDetected / stat.total) * 100).toFixed(1) : '0.0';
        console.log(`${stat.date}: 전체 ${stat.total.toString().padStart(4)}통 | AI ${stat.aiDetected.toString().padStart(4)}통 (${percentage}%)`);
      });
    }
    
    console.log('\n' + '='.repeat(60) + '\n');
    
  } catch (error) {
    console.error('❌ 오류 발생:', error);
    process.exit(1);
  }
}

checkDailyAverage().then(() => {
  process.exit(0);
}).catch((error) => {
  console.error('❌ 실행 오류:', error);
  process.exit(1);
});
